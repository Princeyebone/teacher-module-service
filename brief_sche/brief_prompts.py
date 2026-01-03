"""
Lesson Brief Prompt Builder

Constructs prompts for generating lesson briefs from curriculum data.
"""

from typing import Dict, Any, Optional, List


def build_lesson_brief_prompt(
    subject: str,
    class_name: str,
    previous_lesson: Dict[str, Any],
    todays_lesson: Dict[str, Any],
    weekly_activity: Dict[str, Any],
    teacher_name: Optional[str] = None,
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Build a prompt for generating a quick lesson brief.
    
    Args:
        subject: Subject name
        class_name: Class/grade name
        previous_lesson: Context from the previous lesson
        todays_lesson: Context for today's lesson
        weekly_activity: Weekly activity from course outline
        teacher_name: Optional teacher name for personalization
        retrieved_chunks: Optional list of retrieved lesson design chunks from RAG
        
    Returns:
        A formatted prompt string
    """
    
    # Format previous lesson data
    previous_section = _format_lesson_context("PREVIOUS LESSON", previous_lesson)
    
    # Format today's lesson data
    todays_section = _format_lesson_context("TODAY'S LESSON", todays_lesson)
    
    # Format weekly activity
    weekly_section = _format_weekly_activity(weekly_activity)
    
    # Format retrieved chunks if available
    reference_section = ""
    if retrieved_chunks:
        reference_section = _format_retrieved_chunks(retrieved_chunks)
    
    prompt = f"""You are an expert teaching assistant helping a teacher prepare for their next class. 
The teacher has only 5 MINUTES before class starts and needs a quick, actionable lesson brief.

**SUBJECT:** {subject}
**CLASS:** {class_name}
{f"**TEACHER:** {teacher_name}" if teacher_name else ""}

---
{previous_section}
---
{todays_section}
---
{weekly_section}
---
{reference_section}

**YOUR TASK:**
Generate a concise, actionable LESSON BRIEF that the teacher can read in under 5 minutes. The brief MUST include:

1. **Quick Recap** (1-2 sentences)
   - What was covered in the previous lesson
   - Key concepts students should already know

2. **Lesson Hook** (ABSOLUTELY NON-NEGOTIABLE - THE MOST IMPORTANT PART!)
   
   **WHAT YOU MUST CREATE:**
   A BRUTAL, VISCERAL, UNCOMFORTABLE opening that makes students PHYSICALLY REACT.
   We're talking DROPPED JAWS. WIDE EYES. NERVOUS LAUGHTER. 
   The kind of statement that makes a student elbow their friend and whisper "Did he just say that?!"
   
   **THE HOOK MUST:**
   - Be SAVAGE. Not polite. Not "interesting." SAVAGE.
   - Be DISTURBING (in an educational way) - make them squirm
   - Sound ABSURD or IMPOSSIBLE but be TRUE
   - Be the kind of thing they'll tell their parents at dinner
   - **DIRECTLY RELATE to today's lesson topic** (this is critical!)
   - **END WITH A TRANSITION** that connects the shocking statement to what they'll learn today
   
   **STRUCTURE OF A PERFECT HOOK:**
   [Shocking statement related to the topic] + [Transition: "Today, we'll find out why/how..."]
   
   **EXAMPLES OF HOOKS WITH TRANSITIONS:**
   - "Everyone in this room would be dead right now if not for CO2. Today we'll find out how CO2 keeps you alive." (Carbon Cycle)
   - "Has anyone in this room ever gambled? Lost money? Won? Today we'll find out why the house always wins, and why your gut feeling is mathematically wrong." (Probability)
   - "You share 50% of your DNA with a banana. Are you ready to meet your family? Today we'll explore what DNA really is." (Genetics)
   - "Your body has enough iron to forge a 3-inch nail. Today we'll rip open the human body and see what else we're made of." (Human Biology/Chemistry)
   - "A group of crows is called a 'murder.' A group of flamingos is called a 'flamboyance.' Language is drunk. Today we learn why English makes no sense." (Language/Grammar)
   - "Every time you shuffle a deck of cards, you create a sequence that has NEVER existed before in the history of the universe. Today we'll understand why." (Probability/Permutations)
   - "The chair you're sitting on isn't solid. It's 99.9% empty space. Today we'll find out why you're not falling through the floor." (Atomic Structure)
   
   **ABSOLUTELY FORBIDDEN:**
   - "Have you ever wondered..." - BANNED
   - "Today we're going to explore..." by itself without a hook - BANNED  
   - "Let's think about..." - BANNED
   - Anything a boring teacher would say - BANNED
   - A hook that has NO connection to today's topic - BANNED
   - Being safe, polite, or considerate - BANNED
   
   THE HOOK MUST MAKE STUDENTS FORGET THEY'RE IN SCHOOL FOR 5 SECONDS, THEN SNAP THEM BACK WITH "Today we'll find out..."

3. **Today's Focus** (2-3 sentences)
   - Main topic/concept for today
   - Learning objectives in simple terms

4. **Key Points to Cover** (5-7 bullet points with SUB-POINTS)
   - Cover ALL the important concepts for this lesson
   - Each main point should have 1-2 sub-points with:
     * Clear, simple explanations
     * A concrete example or illustration
     * How it connects to what students already know
   - Make it comprehensive enough that a substitute teacher could use it
   - Include any formulas, definitions, or key vocabulary with explanations

5. **Quick Activity Suggestion** (1-2 sentences)
   - A simple activity or question to engage students mid-lesson
   - How it connects to the weekly goal

6. **Connection to Weekly Goal** (1 sentence)
   - How today's lesson contributes to the week's objective

7. **Ready-to-Use Resources** (REQUIRED - Add this section at the END)
   Write a brief, friendly note to the teacher with EXACTLY these two points:
   
   a) **Presentation Slides**: Let the teacher know that presentation slides have been automatically prepared for this lesson. Mention that they are designed to be easy to present and contain everything needed for the class. Encourage them to check the "Lesson Slides" section.
   
   b) **Student-Specific Support**: Remind the teacher that if any student needs extra help (struggling with the topic, has a disability, learning difficulty, or just needs personalized attention), they can use the "Student Support" feature. Explain briefly: enter the student's name and details, describe what they're struggling with and any special circumstances, and a personalized learning material will be generated specifically for that student - delivered in the student's name to show the teacher went out of their way to help them individually.

**FORMAT:**
- Use clear headings (no emojis, use plain text headers)
- Keep sentences short and direct
- Use bullet points and sub-points where appropriate
- Make it practical and immediately usable
- Total length: 500-700 words (expanded to include comprehensive key points)
- DO NOT use any emojis or special unicode characters
- The LESSON HOOK MUST be BARBARIC, TOPIC-RELATED, and END WITH A TRANSITION like "Today we'll find out..."
- Key Points should be detailed enough that a substitute teacher could teach from them
- The Resources section should feel helpful and supportive, not promotional

**REMEMBER:** This is for a teacher who is about to walk into class. Be concise but comprehensive!

Generate the lesson brief now:
"""
    
    return prompt


def _format_retrieved_chunks(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks for inclusion in the prompt."""
    if not chunks:
        return ""
    
    formatted = "\n**LESSON DESIGN REFERENCE MATERIAL:**\n"
    formatted += "(Use these pedagogical insights to enhance your lesson delivery)\n\n"
    
    for i, chunk in enumerate(chunks, 1):
        text = chunk.get("chunk_text", "")
        # Truncate long chunks
        if len(text) > 600:
            text = text[:600] + "..."
        formatted += f"--- Reference {i} ---\n{text}\n\n"
    
    formatted += "---"
    return formatted


def _format_lesson_context(title: str, lesson_data: Dict[str, Any]) -> str:
    """Format lesson context data into a readable section."""
    
    if not lesson_data or lesson_data == {}:
        return f"""**{title}:**
No previous lesson data available. This may be the first lesson for this class/subject."""
    
    strand = lesson_data.get("strand", "Not specified")
    substrand = lesson_data.get("substrand", "Not specified")
    content_standard = lesson_data.get("content_standard", "Not specified")
    content_standard_code = lesson_data.get("content_standard_code", "")
    indicators = lesson_data.get("indicators", [])
    
    # Format indicators
    indicators_text = ""
    if indicators:
        indicators_list = []
        for ind in indicators:
            if isinstance(ind, dict):
                code = ind.get("code", "")
                text = ind.get("text", "")
                indicators_list.append(f"  - {code}: {text}" if code else f"  - {text}")
            else:
                indicators_list.append(f"  - {ind}")
        indicators_text = "\n".join(indicators_list)
    else:
        indicators_text = "  - None specified"
    
    cs_display = f"{content_standard_code}: {content_standard}" if content_standard_code else content_standard
    
    return f"""**{title}:**
- **Strand:** {strand}
- **Substrand:** {substrand}
- **Content Standard:** {cs_display}
- **Indicators:**
{indicators_text}"""


def _format_weekly_activity(activity_data: Dict[str, Any]) -> str:
    """Format weekly activity data from course outline."""
    
    if not activity_data or activity_data == {}:
        return """**WEEKLY GOAL:**
No weekly activity specified in the course outline."""
    
    week_number = activity_data.get("week_number", "Unknown")
    topic = activity_data.get("topic", "Not specified")
    activity = activity_data.get("activity", "Not specified")
    
    return f"""**WEEKLY GOAL (Week {week_number}):**
- **Topic:** {topic}
- **Activity:** {activity}"""


def build_no_session_brief_prompt(
    subject: str,
    class_name: str,
    teacher_name: Optional[str] = None
) -> str:
    """
    Build a prompt for when there's no session data available.
    """
    return f"""You are an expert teaching assistant. 
A teacher is preparing for their {subject} class ({class_name}) but no specific curriculum data is available.

Generate a brief, encouraging message (50-100 words) that:
1. Acknowledges this is a new teaching context
2. Suggests they review their own lesson plan
3. Offers 2-3 general tips for engaging students in {subject}

Keep it supportive and practical.
"""


# Example usage
if __name__ == "__main__":
    # Test data
    previous = {
        "strand": "Algebra",
        "substrand": "Linear Equations",
        "content_standard": "Solve linear equations in one variable",
        "content_standard_code": "ALG.1.2",
        "indicators": [
            {"code": "ALG.1.2.1", "text": "Solve equations using addition and subtraction"},
            {"code": "ALG.1.2.2", "text": "Solve equations using multiplication and division"}
        ]
    }
    
    todays = {
        "strand": "Algebra",
        "substrand": "Linear Equations",
        "content_standard": "Solve linear equations with variables on both sides",
        "content_standard_code": "ALG.1.3",
        "indicators": [
            {"code": "ALG.1.3.1", "text": "Combine like terms to simplify equations"}
        ]
    }
    
    weekly = {
        "week_number": 3,
        "topic": "Linear Equations and Inequalities",
        "activity": "Problem-solving with real-world applications"
    }
    
    prompt = build_lesson_brief_prompt(
        subject="Mathematics",
        class_name="Grade 8",
        previous_lesson=previous,
        todays_lesson=todays,
        weekly_activity=weekly,
        teacher_name="Mr. Johnson"
    )
    
    print(prompt)
