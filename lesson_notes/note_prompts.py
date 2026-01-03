"""
Lesson Note Prompt Builders

Contains prompt templates and builders for AI-generated lesson note content.
"""

from typing import Dict, Any, Optional


def build_performance_indicator_prompt(
    subject: str,
    class_name: str,
    semester_name: str,
    strand: str,
    substrand: str,
    content_standard: str,
    indicator_text: str,
    country: str
) -> str:
    """
    Build prompt for generating Performance Indicator and Core Competency.
    
    Args:
        subject: Subject name (e.g., "Mathematics")
        class_name: Class name (e.g., "Class 8")
        semester_name: Semester name (e.g., "First Semester 2024")
        strand: Curriculum strand
        substrand: Curriculum substrand
        content_standard: Content standard text
        indicator_text: The specific learning indicator
        country: Country for localization
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are an expert curriculum specialist for {country}. You are helping a teacher prepare a weekly lesson note.

**Context:**
- Country: {country}
- Subject: {subject}
- Class: {class_name}
- Semester: {semester_name}
- Strand: {strand}
- Substrand: {substrand}
- Content Standard: {content_standard}
- Learning Indicator: {indicator_text}

**Task:**
Based on the curriculum information above, generate:

1. **Performance Indicator**: A clear, measurable statement describing what learners should be able to do by the end of this lesson. This should be specific, observable, and aligned with the learning indicator.

2. **Core Competency**: The key skills, knowledge, and attitudes that learners will develop through this lesson. Include relevant 21st-century skills such as critical thinking, creativity, communication, collaboration, digital literacy, or cultural identity as appropriate.

**Output Format (respond in this exact JSON format):**
```json
{{
    "performance_indicator": "By the end of the lesson, learners will be able to...",
    "core_competency": "Critical thinking, problem-solving, ..."
}}
```

Ensure your response is contextually appropriate for {country}'s educational standards and the specified subject/class level.
"""
    return prompt


def build_learner_activities_prompt(
    subject: str,
    class_name: str,
    semester_name: str,
    strand: str,
    substrand: str,
    content_standard: str,
    indicator_text: str,
    country: str,
    performance_indicator: str = ""
) -> str:
    """
    Build prompt for generating Learner Activities and Resources for all 3 phases.
    
    Args:
        subject: Subject name
        class_name: Class name
        semester_name: Semester name
        strand: Curriculum strand
        substrand: Curriculum substrand
        content_standard: Content standard text
        indicator_text: The specific learning indicator
        country: Country for localization
        performance_indicator: Previously generated performance indicator (optional)
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""You are an expert lesson planner for {country}. You are helping a teacher prepare detailed learner activities for a weekly lesson note.

**Context:**
- Country: {country}
- Subject: {subject}
- Class: {class_name}
- Semester: {semester_name}
- Strand: {strand}
- Substrand: {substrand}
- Content Standard: {content_standard}
- Learning Indicator: {indicator_text}
{f'- Performance Indicator: {performance_indicator}' if performance_indicator else ''}

**Task:**
Generate learner activities and teaching/learning resources for the THREE phases of this lesson:

**Phase 1: Starter (5-10 minutes)**
- Engaging warm-up activity to capture attention
- Connect to prior knowledge
- Introduce the lesson objectives
- Activities should be interactive and thought-provoking

**Phase 2: New Learning (25-35 minutes)**
- Main instructional content
- Step-by-step guided practice
- Examples and demonstrations
- Individual or group activities
- Assessment opportunities
- Include specific examples, calculations, or exercises relevant to the indicator

**Phase 3: Reflection (5-10 minutes)**
- Summary of key learning points
- Peer discussion activities
- Formative assessment questions
- Connect learning to real-life applications

**Output Format (respond in this exact JSON format):**
```json
{{
    "phase1": {{
        "activity": "Detailed description of starter activities...",
        "resources": "List of resources needed (e.g., chalk, cards, charts, manipulatives)..."
    }},
    "phase2": {{
        "activity": "Detailed description of main learning activities with examples...",
        "resources": "List of resources needed..."
    }},
    "phase3": {{
        "activity": "Detailed description of reflection activities...",
        "resources": "List of resources needed..."
    }}
}}
```

**Guidelines:**
1. Activities should be age-appropriate for {class_name}
2. Use locally available resources common in {country}
3. Include specific examples, problems, or exercises where applicable
4. Activities should be interactive and promote learner participation
5. Ensure activities directly address the learning indicator
6. Be detailed and practical - teachers should be able to follow directly
"""
    return prompt


def parse_performance_indicator_response(ai_response: str) -> Dict[str, str]:
    """
    Parse AI response for performance indicator and core competency.
    
    Args:
        ai_response: Raw AI response text
        
    Returns:
        Dict with 'performance_indicator' and 'core_competency' keys
    """
    import json
    import re
    
    result = {
        "performance_indicator": "",
        "core_competency": ""
    }
    
    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{[^{}]*"performance_indicator"[^{}]*\}', ai_response, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            result["performance_indicator"] = parsed.get("performance_indicator", "")
            result["core_competency"] = parsed.get("core_competency", "")
        else:
            # Try direct JSON parse
            parsed = json.loads(ai_response.strip())
            result["performance_indicator"] = parsed.get("performance_indicator", "")
            result["core_competency"] = parsed.get("core_competency", "")
    except (json.JSONDecodeError, AttributeError):
        # Fallback: Try to extract content manually
        lines = ai_response.split('\n')
        for line in lines:
            line_lower = line.lower()
            if 'performance indicator' in line_lower or 'performance_indicator' in line_lower:
                result["performance_indicator"] = line.split(':', 1)[-1].strip().strip('"')
            elif 'core competency' in line_lower or 'core_competency' in line_lower:
                result["core_competency"] = line.split(':', 1)[-1].strip().strip('"')
    
    return result


def parse_learner_activities_response(ai_response: str) -> Dict[str, Dict[str, str]]:
    """
    Parse AI response for learner activities and resources.
    
    Args:
        ai_response: Raw AI response text
        
    Returns:
        Dict with 'phase1', 'phase2', 'phase3' keys, each containing 'activity' and 'resources'
    """
    import json
    import re
    
    result = {
        "phase1": {"activity": "", "resources": ""},
        "phase2": {"activity": "", "resources": ""},
        "phase3": {"activity": "", "resources": ""}
    }
    
    try:
        # Try to find JSON block
        json_match = re.search(r'\{[\s\S]*"phase1"[\s\S]*"phase2"[\s\S]*"phase3"[\s\S]*\}', ai_response)
        if json_match:
            # Clean up the JSON string
            json_str = json_match.group()
            # Replace any markdown code block markers
            json_str = re.sub(r'```json\s*', '', json_str)
            json_str = re.sub(r'```\s*', '', json_str)
            
            parsed = json.loads(json_str)
            for phase in ['phase1', 'phase2', 'phase3']:
                if phase in parsed:
                    result[phase]["activity"] = parsed[phase].get("activity", "")
                    result[phase]["resources"] = parsed[phase].get("resources", "")
        else:
            # Try direct parse
            cleaned = ai_response.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```json?\s*', '', cleaned)
                cleaned = re.sub(r'```\s*$', '', cleaned)
            parsed = json.loads(cleaned)
            for phase in ['phase1', 'phase2', 'phase3']:
                if phase in parsed:
                    result[phase]["activity"] = parsed[phase].get("activity", "")
                    result[phase]["resources"] = parsed[phase].get("resources", "")
    except (json.JSONDecodeError, AttributeError) as e:
        # Return empty structure if parsing fails
        pass
    
    return result


# Default fallback values
DEFAULT_PHASE_ACTIVITIES = {
    "phase1": {
        "activity": "Engage learners with a warm-up activity related to the topic. Ask questions to activate prior knowledge.",
        "resources": "Whiteboard, markers"
    },
    "phase2": {
        "activity": "Present the main content with examples. Guide learners through practice exercises.",
        "resources": "Textbook, worksheets, manipulatives"
    },
    "phase3": {
        "activity": "Facilitate class discussion on key learnings. Summarize the lesson and assign homework.",
        "resources": "Exercise books"
    }
}
