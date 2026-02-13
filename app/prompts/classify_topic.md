Analyze the following data:
<topic>
{topic}
</topic>

<quiz_json>
{quiz_json}
</quiz_json>

TASK:
1. Is this topic too broad to provide a specific, high-quality gift recommendation given the recipient's profile?
2. IMPORTANT: Check the Quiz Data. If the answer to "narrow it down" is already evident in their interests or profile, set "is_wide": false and use that info to provide a "refined_topic".
3. If it's truly too broad:
   - Provide 3-4 specific sub-topics or "branches".
   - Provide a polite 'question' in {language} to help narrow it down.
4. If it's specific enough:
   - Provide a 'refined_topic' that incorporates details from the quiz.

Return ONLY a JSON object:
{{
    "is_wide": boolean,
    "branches": ["branch 1", "branch 2", ...],
    "question": "string or null",
    "refined_topic": "string or null"
}}
