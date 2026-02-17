<topic>
{topic}
</topic>

<quiz_json>
{quiz_json}
</quiz_json>

<liked_concepts>
{liked_concepts}
</liked_concepts>

<disliked_concepts>
{disliked_concepts}
</disliked_concepts>

<shown_concepts>
{shown_concepts}
</shown_concepts>

TASK:
1. Analyze the recipient's life context and Gifting Gaps.
2. Generate 3-4 NEW specific gift hypotheses for the topic "{topic}".
3. IMPORTANT: 
   - DIVERSITY: Each hypothesis must represent a unique angle or a different Gifting Gap. Do not provide 3 variations of the same item.
   - LIKED CONCEPTS: These are your "North Star" indicators of what works. Use them to understand the recipient's taste and psychological profile, but DO NOT simply repeat them or suggest very similar items. Explore "sister" interests or higher-level themes they imply.
   - DISLIKED CONCEPTS: Strictly avoid these, user rejected them.
   - PREVIOUSLY SHOWN: Do not repeat these. suggets something NEW.

For each hypothesis, provide:
- title: Catchy name.
- description: Why this fits.
- primary_gap: the_mirror, the_optimizer, the_catalyst, the_anchor, or the_permission.
- reasoning: Psychological why, linking back to specific details in the quiz data.
- search_queries: 3-5 keywords for product search.

Return ONLY JSON list of objects.
