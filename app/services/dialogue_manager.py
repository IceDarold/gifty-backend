import uuid
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from recommendations.models import (
    RecommendationSession, 
    QuizAnswers, 
    DialogueStep, 
    Hypothesis,
    RecipientProfile,
    RecipientResponse,
    Language,
    TopicTrack,
    UserInteraction
)
from app.services.i18n import i18n, TranslationKey
from app.services.i18n import i18n, TranslationKey
from app.services.ai_reasoning_service import AIReasoningService
from app.services.recommendation import RecommendationService
from app.services.session_storage import SessionStorage, get_session_storage
from app.services.recipient_service import RecipientService
from app.services.notifications import get_notification_service

logger = logging.getLogger(__name__)

class DialogueManager:
    def __init__(
        self, 
        ai_service: AIReasoningService,
        recommendation_service: RecommendationService,
        session_storage: SessionStorage,
        db: Optional[AsyncSession] = None,
        recipient_service: Optional[any] = None
    ):
        self.ai_service = ai_service
        self.recommendation_service = recommendation_service
        self.session_storage = session_storage
        self.db = db
        self.recipient_service = recipient_service or (RecipientService(db) if db else None)

    async def init_session(self, quiz: QuizAnswers, user_id: Optional[uuid.UUID] = None) -> RecommendationSession:
        """Starts a new discovery session based on quiz answers."""
        session_id = str(uuid.uuid4())
        profile = RecipientProfile(
            findings=[], 
            required_effort=quiz.effort_level,
            deadline_days=quiz.deadline_days,
            budget=quiz.budget,
            language=quiz.language,
            quiz_data=quiz
        )
        
        # Save recipient to database if db is available
        recipient_id = None
        if self.recipient_service and user_id:
            try:
                db_recipient = await self.recipient_service.create_recipient(
                    user_id=user_id,
                    profile=profile
                )
                recipient_id = db_recipient.id
                # Update profile with DB ID
                profile.id = str(recipient_id)
                profile.owner_id = str(user_id)
                logger.info(f"Saved recipient {recipient_id} to database")
            except Exception as e:
                logger.error(f"Failed to save recipient to database: {e}")
        
        session = RecommendationSession(
            session_id=session_id,
            recipient=RecipientResponse(
                id=profile.id,
                name=profile.name
            ),
            full_recipient=profile,
            language=quiz.language
        )
        
        # 1. Normalize and split topics
        try:
            normalized_topics = await self.ai_service.normalize_topics(
                quiz.interests, 
                language=session.language
            )
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            normalized_topics = []
            # Proactive notification
            notifier = get_notification_service()
            await notifier.notify(
                topic="ai_error",
                message=f"Normalization failed for session {session_id}",
                data={"error": str(e), "input": quiz.interests}
            )

        session.topics = normalized_topics or quiz.interests

        if not session.topics:
            # Generate a deep psychological question instead of a hardcoded one
            quiz_dict = session.full_recipient.quiz_data.dict() if session.full_recipient.quiz_data else {}
            try:
                probe_data = await self.ai_service.generate_personalized_probe(
                    context_type="dead_end",
                    quiz_data=quiz_dict,
                    language=session.language
                )
                session.current_probe = DialogueStep(
                    question=probe_data.get("question"),
                    options=probe_data.get("options", [])
                )
            except Exception:
                session.current_probe = DialogueStep(
                    question=i18n.translate(TranslationKey.NO_INTERESTS_DEAD_END, session.language),
                    options=[]
                )
            await self.session_storage.save_session(session)
            return session

        # 2. Bulk Track Generation (One API call for all topics)
        try:
            topics_to_process = list(session.topics)
            
            # Pass raw quiz data for deep LLM-native diagnostic
            quiz_dict = session.full_recipient.quiz_data.model_dump() if session.full_recipient.quiz_data else {}
            
            # Single bulk call
            bulk_data = await self.ai_service.generate_hypotheses_bulk(
                topics=topics_to_process,
                quiz_data=quiz_dict,
                liked_concepts=session.full_recipient.liked_labels,
                disliked_concepts=session.full_recipient.ignored_labels,
                language=session.language
            )
            
            # Process results and fetch previews
            tasks = []
            for topic in topics_to_process:
                topic_data = bulk_data.get(topic, {})
                if not topic_data:
                     # Fallback matching for case-insensitivity
                     for k, v in bulk_data.items():
                         if k.lower() == topic.lower():
                             topic_data = v
                             break
                
                tasks.append(self._create_track_from_data(session, topic, topic_data))
                
            session.tracks = await asyncio.gather(*tasks)
            
            # 3. Persist Hypotheses to DB (only specific ones)
            if self.recipient_service:
                recipient_uuid = uuid.UUID(session.full_recipient.id) if session.full_recipient.id else None
                for track in session.tracks:
                    if track.status == "ready":
                        await self.recipient_service.save_hypotheses(
                            session_id=session.session_id,
                            recipient_id=recipient_uuid,
                            track_title=track.topic_name,
                            hypotheses=track.hypotheses
                        )
            
        except Exception as e:
            logger.error(f"DialogueManager: Error in bulk track generation: {e}", exc_info=True)
            # Proactive notification
            notifier = get_notification_service()
            await notifier.notify(
                topic="ai_error",
                message=f"Bulk track generation failed for session {session_id}",
                data={"error": str(e), "topics": topics_to_process}
            )
            
            if session.topics:
                # Fallback: Attempt individual track generation for ALL topics (Parallel)
                logger.info(f"DialogueManager: Falling back to individual track generation for {len(session.topics)} topics")
                tasks = [self._create_track_for_topic(session, topic) for topic in session.topics]
                session.tracks = await asyncio.gather(*tasks, return_exceptions=False)
        
        # Set first track as active for compatibility
        if session.tracks:
            first_track = session.tracks[0]
            session.selected_topic_id = first_track.topic_id
            
        await self.session_storage.save_session(session)
        return session

    async def _create_track_from_data(self, session: RecommendationSession, topic: str, raw_data: Dict[str, Any]) -> TopicTrack:
        """Internal helper to convert raw AI topic data into a Track."""
        
        # Scenario 1: Topic is too wide (AI requested branching)
        if raw_data.get("is_wide"):
            return TopicTrack(
                topic_id=str(uuid.uuid4()),
                topic_name=topic,
                status="question",
                question=DialogueStep(
                    question=raw_data.get("question") or i18n.translate(TranslationKey.BRANCHING_QUESTION_DEFAULT, session.language, topic=topic),
                    options=raw_data.get("branches", []),
                    context_tags=[f"topic:{topic}"]
                )
            )

        # Scenario 2: Topic is specific, process hypotheses
        raw_hypotheses = raw_data.get("hypotheses", [])
        
        if not raw_hypotheses:
            # Fallback if AI returned nothing for this topic
            quiz_dict = session.full_recipient.quiz_data.model_dump() if session.full_recipient.quiz_data else {}
            try:
                probe_data = await self.ai_service.generate_personalized_probe(
                    context_type="exploration",
                    quiz_data=quiz_dict,
                    topic=topic,
                    language=session.language
                )
                return TopicTrack(
                    topic_id=str(uuid.uuid4()),
                    topic_name=topic,
                    status="question",
                    question=DialogueStep(
                        question=probe_data.get("question"),
                        options=probe_data.get("options", []),
                        context_tags=[f"topic:{topic}"]
                    )
                )
            except Exception:
                return TopicTrack(
                    topic_id=str(uuid.uuid4()),
                    topic_name=topic,
                    status="question",
                    question=DialogueStep(
                        question=i18n.translate(TranslationKey.TELL_ME_MORE_ABOUT_TOPIC, session.language, topic=topic),
                        options=[],
                        context_tags=[f"topic:{topic}"]
                    )
                )

        # Fetch previews for specific hypotheses
        async def _fill_hypothesis(rh: dict) -> Hypothesis:
            h_id = str(uuid.uuid4())
            try:
                previews = await self.recommendation_service.find_preview_products(
                    search_queries=rh.get("search_queries", []),
                    hypothesis_title=rh.get("title", ""),
                    max_price=session.full_recipient.budget,
                    session_id=session.session_id,
                    hypothesis_id=uuid.UUID(h_id),
                    track_title=topic
                )
            except Exception as e:
                logger.error(f"Failed to fetch previews for hypothesis {rh.get('title')}: {e}")
                previews = []

            return Hypothesis(
                id=h_id,
                title=rh.get("title", "Idea"),
                description=rh.get("description", ""),
                reasoning=rh.get("reasoning", ""),
                primary_gap=rh.get("primary_gap", "the_mirror"),
                preview_products=previews,
                search_queries=rh.get("search_queries", [])
            )

        hypotheses = await asyncio.gather(*[_fill_hypothesis(rh) for rh in raw_hypotheses])
        
        return TopicTrack(
            topic_id=str(uuid.uuid4()),
            topic_name=topic,
            status="ready",
            title=i18n.translate(TranslationKey.TRACK_DIRECTION_TITLE, session.language, topic=topic),
            preview_text=i18n.translate(TranslationKey.TRACK_PREVIEW_TEXT, session.language, topic=topic),
            hypotheses=hypotheses
        )

    async def _create_track_for_topic(self, session: RecommendationSession, topic: str) -> TopicTrack:
        """Internal helper to generate a full track for a topic (Single topic entry)."""
        logger.info(f"DialogueManager: Creating track for topic '{topic}'")
        
        # 1. Classify (determine if wide)
        quiz_dict = session.full_recipient.quiz_data.dict() if session.full_recipient.quiz_data else {}
        try:
            classification = await self.ai_service.classify_topic(topic, quiz_data=quiz_dict, language=session.language)
        except Exception as e:
            logger.error(f"DialogueManager: Classification failed for topic '{topic}': {e}")
            classification = {"is_wide": False, "refined_topic": topic}
            notifier = get_notification_service()
            await notifier.notify(
                topic="ai_error",
                message=f"Classification failed for topic '{topic}'",
                data={"error": str(e)}
            )
        
        if classification.get("is_wide"):
            return await self._create_track_from_data(session, topic, classification)

        refined_topic = classification.get("refined_topic") or topic
        
        # Collect ALL shown titles in session for global deduplication
        all_shown = [h.title for t in session.tracks for h in t.hypotheses]
        
        # 2. Generate Hypotheses for the refined topic
        raw_hypotheses = await self.ai_service.generate_hypotheses(
            topic=refined_topic,
            quiz_data=quiz_dict,
            liked_concepts=session.full_recipient.liked_labels,
            disliked_concepts=session.full_recipient.ignored_labels,
            shown_concepts=all_shown, 
            language=session.language
        )
        
        # 3. Build the track
        return await self._create_track_from_data(session, topic, {"hypotheses": raw_hypotheses})

    async def interact(self, session_id: str, action: str, value: Optional[str] = None, metadata: Dict[str, Any] = {}) -> RecommendationSession:
        """Handles user interaction (answering probes, liking hypotheses, etc.)"""
        session = await self.session_storage.get_session(session_id)
        if not session:
            logger.error(f"DialogueManager.interact: Session {session_id} not found in storage")
            raise ValueError("Session not found")

        # 1. Record Interaction in Profile
        interaction = UserInteraction(
            type=action,
            timestamp=datetime.now().timestamp(),
            target_id=value if value else "unknown",
            target_type="hypothesis" if "hypothesis" in action else "product" if "gift" in action else "navigation",
            value=value,
            metadata=metadata
        )
        session.full_recipient.interactions.append(interaction)
        
        # Optimization: Limit session interaction history size to avoid Redis bloat
        # full history is still persisted to the SQL DB below.
        if len(session.full_recipient.interactions) > 30:
            session.full_recipient.interactions = session.full_recipient.interactions[-30:]
        
        # Sync interaction to DB
        if self.recipient_service and session.full_recipient.id:
            try:
                await self.recipient_service.save_interaction(
                    recipient_id=uuid.UUID(session.full_recipient.id),
                    session_id=session_id,
                    interaction=interaction
                )
            except Exception as e:
                logger.error(f"Failed to sync interaction to DB for session {session_id}: {e}")

        # 2. Handle Action Logic
        if action in ["answer_probe", "select_branch"]:
            topic_id = metadata.get("topic_id")
            answer_text = value
            track = next((t for t in session.tracks if t.topic_id == topic_id), None)
            
            if track:
                logger.info(f"DialogueManager: Refining track '{track.topic_name}' with answer: '{answer_text}'")
                refined_query = f"{track.topic_name} (context: {answer_text})"
                new_track = await self._create_track_for_topic(session, refined_query)
                for i, t in enumerate(session.tracks):
                    if t.topic_id == topic_id:
                        session.tracks[i] = new_track
                        session.selected_topic_id = new_track.topic_id
                        break
            else:
                logger.info(f"DialogueManager: Creating new track from answer: '{answer_text}'")
                new_track = await self._create_track_for_topic(session, answer_text)
                session.tracks.append(new_track)
                session.selected_topic_id = new_track.topic_id

        elif action == "suggest_topics":
            logger.info(f"DialogueManager: Generating topic hints for session {session_id}")
            quiz_dict = session.full_recipient.quiz_data.model_dump() if session.full_recipient.quiz_data else {}
            existing_topics = [t.topic_name for t in session.tracks]
            
            hints = await self.ai_service.generate_topic_hints(
                quiz_data=quiz_dict,
                topics_explored=existing_topics,
                language=session.language
            )
            session.topic_hints = hints

        elif action == "select_track":
            track = next((t for t in session.tracks if t.topic_id == value), None)
            if track:
                session.selected_topic_id = track.topic_id
            else:
                logger.error(f"DialogueManager: Track {value} not found")

        elif action == "load_more_hypotheses":
            # Pagination-like logic: Append more ideas without judgment on current ones
            topic_id = value or metadata.get("topic_id")
            track = next((t for t in session.tracks if t.topic_id == topic_id), None)
            
            if track:
                logger.info(f"DialogueManager: Loading more hypotheses for track '{track.topic_name}'")
                
                # Context for LLM - Global shown concepts to avoid cross-topic repetition
                quiz_dict = session.full_recipient.quiz_data.model_dump() if session.full_recipient.quiz_data else {}
                all_shown = [h.title for t in session.tracks for h in t.hypotheses]
                
                raw_new = await self.ai_service.generate_hypotheses(
                    topic=track.topic_name,
                    quiz_data=quiz_dict,
                    liked_concepts=session.full_recipient.liked_labels,
                    disliked_concepts=session.full_recipient.ignored_labels,
                    shown_concepts=all_shown,
                    language=session.language
                )
                
                # Convert to Hypothesis objects with previews
                new_hypos = []
                for rh in raw_new:
                    previews = await self.recommendation_service.find_preview_products(
                        search_queries=rh.get("search_queries", []),
                        hypothesis_title=rh.get("title", ""),
                        max_price=session.full_recipient.budget
                    )
                    new_hypos.append(Hypothesis(
                        id=str(uuid.uuid4()),
                        title=rh.get("title", "Concept"),
                        description=rh.get("description", ""),
                        reasoning=rh.get("reasoning", ""),
                        primary_gap=rh.get("primary_gap", "the_mirror"),
                        preview_products=previews,
                        search_queries=rh.get("search_queries", [])
                    ))
                
                # APPEND instead of replacing
                track.hypotheses.extend(new_hypos)
                
                # PERSIST new hypotheses to DB
                if self.recipient_service:
                    try:
                        recipient_uuid = uuid.UUID(session.full_recipient.id) if session.full_recipient.id else None
                        await self.recipient_service.save_hypotheses(
                            session_id=session.session_id,
                            recipient_id=recipient_uuid,
                            track_title=track.topic_name,
                            hypotheses=new_hypos
                        )
                    except Exception as e:
                        logger.error(f"Failed to persist additional hypotheses to DB: {e}")
            else:
                logger.error(f"DialogueManager: Cannot load more, track '{topic_id}' not found")

        elif action == "like_hypothesis":
            if value not in session.liked_hypotheses:
                session.liked_hypotheses.append(value)
                session.full_recipient.liked_hypotheses.append(value)
                
                # Find title for LLM context
                for t in session.tracks:
                    h_obj = next((h for h in t.hypotheses if h.id == value), None)
                    if h_obj and h_obj.title not in session.full_recipient.liked_labels:
                        session.full_recipient.liked_labels.append(h_obj.title)
                        # Sync Liked Reaction to Hypothesis Table
                        if self.recipient_service:
                            await self.recipient_service.update_hypothesis_reaction(uuid.UUID(value), "like")
                        break
            
            session.selected_hypothesis_id = value
            
            # Find the hypothesis for deep dive
            hypothesis = None
            for t in session.tracks:
                hypothesis = next((h for h in t.hypotheses if h.id == value), None)
                if hypothesis: break
            
            if hypothesis:
                logger.info(f"DialogueManager: Generating Deep Dive products for hypothesis {value}")
                products = await self.recommendation_service.get_deep_dive_products(
                    search_queries=hypothesis.search_queries,
                    hypothesis_title=hypothesis.title,
                    hypothesis_description=hypothesis.description,
                    max_price=session.full_recipient.budget,
                    session_id=session_id,
                    hypothesis_id=uuid.UUID(value) if value else None,
                    track_title=None # Could find from track if needed
                )
                hypothesis.preview_products = products
            else:
                logger.error(f"DialogueManager: Hypothesis {value} not found in session")

        elif action == "unlike_hypothesis":
            if value in session.liked_hypotheses:
                session.liked_hypotheses.remove(value)
                session.full_recipient.liked_hypotheses.remove(value)
                # We don't necessarily remove from labels because it was an "interest" once
                # But if we want strict toggle:
                for t in session.tracks:
                    h_obj = next((h for h in t.hypotheses if h.id == value), None)
                    if h_obj and h_obj.title in session.full_recipient.liked_labels:
                        session.full_recipient.liked_labels.remove(h_obj.title)
                        # Sync Unlike to DB (Reset reaction)
                        if self.recipient_service:
                            await self.recipient_service.update_hypothesis_reaction(uuid.UUID(value), None)
                        break

        elif action == "select_gift":
            if value not in session.full_recipient.shortlist:
                session.full_recipient.shortlist.append(value)

        elif action == "dislike_hypothesis":
            if value not in session.ignored_hypotheses:
                session.ignored_hypotheses.append(value)
                session.full_recipient.ignored_hypotheses.append(value)
                
                # Find title for LLM context
                for t in session.tracks:
                    h_obj = next((h for h in t.hypotheses if h.id == value), None)
                    if h_obj and h_obj.title not in session.full_recipient.ignored_labels:
                        session.full_recipient.ignored_labels.append(h_obj.title)
                        # Sync Dislike to DB
                        if self.recipient_service:
                            await self.recipient_service.update_hypothesis_reaction(uuid.UUID(value), "dislike")
                        break

        elif action == "undislike_hypothesis":
            if value in session.ignored_hypotheses:
                session.ignored_hypotheses.remove(value)
                session.full_recipient.ignored_hypotheses.remove(value)
                for t in session.tracks:
                    h_obj = next((h for h in t.hypotheses if h.id == value), None)
                    if h_obj and h_obj.title in session.full_recipient.ignored_labels:
                        session.full_recipient.ignored_labels.remove(h_obj.title)
                        # Sync Undislike to DB (Reset)
                        if self.recipient_service:
                            await self.recipient_service.update_hypothesis_reaction(uuid.UUID(value), None)
                        break

        await self.session_storage.save_session(session)
        return session
