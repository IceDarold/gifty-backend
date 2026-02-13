import json
import asyncio
import os
from datetime import datetime
from typing import List, Dict, Any

from app.services.anthropic_service import AnthropicService
from recommendations.models import QuizAnswers, RecipientProfile

# --- Judge Prompt ---
JUDGE_PROMPT = """
You are a Quality Assurance Specialist for a gifting AI. 
Evaluate the following gift hypotheses based on these criteria (1-5 points each):
1. **GUTG Alignment**: Does the hypothesis actually match the assigned Gifting Gap?
2. **Creativity**: Is it better than a generic "Gift Card" or "Socks"?
3. **Psychology**: Does it address the user's specific "Pain Points" mentioned in the context?
4. **Searchability**: Are the search queries specific enough to find good products?

Return your evaluation in Markdown format.
"""

async def run_evaluation():
    anthropic = AnthropicService()
    
    # Load scenarios
    with open("tests/eval/scenarios.json", "r") as f:
        scenarios = json.load(f)
    
    report_md = f"# Model Evaluation Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    report_md += "## Summary\n| Scenario | Total Hypotheses | GPT-Grade | Manual Review |\n| :--- | :--- | :--- | :--- |\n"
    
    details_md = "## Detailed Results\n\n"
    
    for case in scenarios:
        print(f"Processing: {case['name']}...")
        quiz = QuizAnswers(**case['quiz'])
        quiz_data = quiz.dict()
        
        # 1. Generate Hypotheses with new AI-native diagnostic
        try:
            hypotheses = await anthropic.generate_hypotheses(
                topic=case['topic'], 
                quiz_data=quiz_data,
                language=quiz.language
            )
            
            # --- Build Report Detail ---
            details_md += f"### Case: {case['name']}\n"
            details_md += f"**Input Topic:** {case['topic']}\n\n"
            
            details_md += "| Gap | Title | Reasoning | Queries |\n| :--- | :--- | :--- | :--- |\n"
            for h in hypotheses:
                queries = ", ".join(h.get('search_queries', [])[:2])
                details_md += f"| {h['primary_gap']} | **{h['title']}** | {h['reasoning']} | *{queries}* |\n"
            
            details_md += "\n---\n"
            report_md += f"| {case['name']} | ✅ Success | - | [View Details](#case-{case['id']}) |\n"
            
        except Exception as e:
            print(f"Error in {case['name']}: {e}")
            report_md += f"| {case['name']} | ❌ Failed | - | - |\n"

    # Save report
    os.makedirs("reports", exist_ok=True)
    with open("reports/eval_results.md", "w") as f:
        f.write(report_md + "\n" + details_md)
    
    print("\nEvaluation complete! Open reports/eval_results.md to see the results.")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
