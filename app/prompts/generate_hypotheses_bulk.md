I have the following data for gift recommendation analysis:
<topics>
{topics_str}
</topics>

<quiz_json>
{quiz_json}
</quiz_json>

<liked_concepts>
{liked_concepts}
</liked_concepts>

<disliked_concepts>
{disliked_concepts}
</disliked_concepts>

TASK:
1. Perform a deep psychological "diagnostic" of the recipient based on the quiz data. 
2. For EACH topic in the list:
   - Step A: Determine if the topic is too broad (e.g., "Music", "Video Games", "Decor") to give meaningful, specific recommendations.
   - Step B: 
     - IF TOO BROAD: Set "is_wide": true. Provide 3-4 "branches" (sub-topics) and a polite "question" in {language} to help narrow it down.
     - IF SPECIFIC: Set "is_wide": false. Generate 2-3 specific GUTG hypotheses (diverse across Mirror, Optimizer, Catalyst, Anchor, Permission).
3. Ensure every specific hypothesis has search_queries, reasoning, and a primary_gap.

Return ONLY a JSON object where keys are the input topics:
{{
    "Topic Name 1": {{
        "is_wide": true,
        "question": "Which area of Music does he prefer?",
        "branches": ["Vinyl records", "Concert tickets", "Studio gear"]
    }},
    "Topic Name 2": {{
        "is_wide": false,
        "hypotheses": [
            {{
                "title": "...",
                "description": "...",
                "primary_gap": "...",
                "reasoning": "...",
                "search_queries": ["...", "..."]
            }}
        ]
    }}
}}
