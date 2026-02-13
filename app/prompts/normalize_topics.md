I have a list of raw interest topics from a user quiz in the `<topics>` tag below:
<topics>
{topics}
</topics>
Normalize them. 
- Split combined topics (e.g., "Reading and wine" -> ["Reading", "Wine"])
- Correct typos.
- Standardize naming.
- Ensure they are in {language}.

Return ONLY valid JSON list of strings.
