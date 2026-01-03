# Class Name vs Pupils - Usage Clarification

## ✅ Important Distinction Implemented!

The Free Plan endpoint now correctly uses:
- **`class_name`** for database queries (timetable lookups)
- **`pupils`** for AI prompt targeting (curriculum level)

---

## 🎯 Why This Separation?

### The Problem
Teachers organize their timetables by **class names** (e.g., "Class A", "Section 1", "2B") but the AI needs **pupil levels** (e.g., "Grade 4", "Level 100") for accurate curriculum targeting.

### The Solution
Use **both fields** for their specific purposes:

| Field | Purpose | Example Values | Used For |
|-------|---------|---------------|----------|
| `class_name` | Database identifier | "Class A", "Section 1", "2B" | Timetable queries |
| `pupils` | Curriculum level | "Grade 4", "Level 100", "Form 3" | AI targeting |

---

## 📝 Implementation

### Request Model
```json
{
  "subject": "Mathematics",
  "class_name": "Class A",        ← Used for database
  "pupils": "Grade 4",            ← Used for AI
  "academic_level": "k12",
  "education_system": "Ghana"
}
```

### Database Query (Using class_name)
```python
# Query timetable using class_name
timetable_result = await session.execute(
    select(WeeklyTimeTable)
    .where(WeeklyTimeTable.teacher_id == current_teacher.id)
    .where(WeeklyTimeTable.subject == request.subject)
    .where(WeeklyTimeTable.pupils == request.class_name)  # ← class_name for DB
)
```

**Why?** Timetable entries are stored with the class name the teacher uses (e.g., "Class A")

### AI Prompt (Using pupils)
```python
# Prompt builder uses pupils for curriculum targeting
prompt = build_free_plan_prompt(
    subject=subject,
    class_name=class_name,
    pupils=pupils,  # ← pupils for AI targeting
    ...
)
```

**Prompt includes:**
```
WEB SEARCH REQUIREMENTS:
- **First Term semester** curriculum for Grade 4 in Mathematics
- Syllabus for Grade 4 - **First Term specific**
...

EDUCATIONAL CONTEXT:
- Class Name/Section: Class A
- **PUPIL/CLASS LEVEL: Grade 4** ← PRIMARY level indicator
```

**Why?** AI needs the actual grade/level to search for appropriate curriculum

---

## 🔍 Example Scenarios

### Scenario 1: Basic School
**Input:**
```json
{
  "subject": "Mathematics",
  "class_name": "Blue Class",     ← Timetable identifier
  "pupils": "Class 4",            ← Curriculum level
  "academic_level": "k12",
  "education_system": "Ghana"
}
```

**Database Query:**
- Searches for: `subject=Mathematics AND pupils='Blue Class'`
- Finds timetable entries for "Blue Class"

**AI Targeting:**
- Searches for: "Class 4 Mathematics Ghana curriculum"
- Gets appropriate Class 4 level content

---

### Scenario 2: University
**Input:**
```json
{
  "subject": "Computer Science",
  "class_name": "CS101-A",        ← Section identifier
  "pupils": "Level 100",          ← Year level
  "academic_level": "university",
  "education_system": "Ghana"
}
```

**Database Query:**
- Searches for: `subject=Computer Science AND pupils='CS101-A'`
- Finds timetable entries for section "CS101-A"

**AI Targeting:**
- Searches for: "Level 100 Computer Science Ghana curriculum"
- Gets appropriate first-year university content

---

### Scenario 3: Secondary School
**Input:**
```json
{
  "subject": "Biology",
  "class_name": "3A",             ← Class section
  "pupils": "Form 3",             ← Year group
  "academic_level": "k12",
  "education_system": "Cambridge IGCSE"
}
```

**Database Query:**
- Searches for: `subject=Biology AND pupils='3A'`
- Finds timetable entries for class "3A"

**AI Targeting:**
- Searches for: "Form 3 Biology Cambridge IGCSE curriculum"
- Gets Form 3 level content

---

## 📊 Data Flow

```
Teacher Input
├─ class_name: "Class A"
│  └─ Database Query
│     └─ WHERE pupils = 'Class A'
│        └─ Finds: Timetable entries
│
└─ pupils: "Grade 4"
   └─ AI Prompt
      └─ "Generate for Grade 4"
         └─ AI searches: "Grade 4 curriculum"
            └─ Returns: Grade 4 level content
```

---

## 🔄 Complete Flow

```
1. Request Received
   {
     "class_name": "Class A",
     "pupils": "Grade 4",
     "subject": "Mathematics"
   }

2. Database Query (using class_name)
   ↓
   SELECT * FROM weeklytimetable
   WHERE subject = 'Mathematics'
     AND pupils = 'Class A'
   ↓
   Returns: Timetable for Class A

3. Build Session Data
   ↓
   Weekly sessions for Class A's schedule

4. AI Prompt (using pupils)
   ↓
   "Generate Grade 4 Mathematics curriculum..."
   ↓
   AI searches web for Grade 4 content

5. Store Results (using class_name)
   ↓
   Store in DB with class_name = 'Class A'
```

---

## 📋 Logging Output

```
====================================================================================================
  REQUEST PARAMETERS
====================================================================================================
Subject: Mathematics
Class Name: Class A              ← For database
Pupils/Level: Grade 4            ← For AI
Academic Level: k12
Education System: Ghana

====================================================================================================
  GATHERING SESSION DATA
====================================================================================================
Fetching weekly timetable...
Querying DB for: Subject=Mathematics, Class=Class A     ← Database query
AI Targeting: Pupils=Grade 4                            ← AI will use this
✅ Found 3 timetable entries

====================================================================================================
  WEB SEARCH CONFIGURATION
====================================================================================================
Search Context - Class: Class A                         ← Section/class
Search Context - Pupils/Level: Grade 4 ← PRIMARY TARGETING  ← AI targeting
```

---

## ✅ Benefits of This Approach

### 1. Flexible Class Organization
Teachers can name their classes however they want:
- "Red Class", "Blue Class"
- "Section A", "Section B"
- "1A", "1B", "1C"
- "Morning Class", "Afternoon Class"

### 2. Accurate Curriculum Targeting
AI always gets the correct level:
- "Grade 4" → Grade 4 curriculum
- "Level 100" → First year university
- "Form 3" → Third year secondary

### 3. Database Consistency
Timetable entries use the class name teachers actually use in their schedule

### 4. Clear Separation of Concerns
- **class_name** = Organizational/scheduling
- **pupils** = Educational level/curriculum

---

## 🎯 Field Definitions

### class_name
- **Purpose**: Identify the class/section in timetable
- **Examples**: "Class A", "Section 1", "2B", "CS101-A"
- **Used in**: Database queries, storage
- **Maps to**: Timetable organization

### pupils
- **Purpose**: Specify curriculum level for AI
- **Examples**: "Grade 4", "Level 100", "Form 3", "Class 2"
- **Used in**: AI prompts, web search
- **Maps to**: Educational standards

---

## 🧪 Testing

### Test Case 1: Matching Values
```json
{
  "class_name": "Grade 4",
  "pupils": "Grade 4"
}
```
Works if timetable uses "Grade 4" as class name

### Test Case 2: Different Values (Common)
```json
{
  "class_name": "Class A",
  "pupils": "Grade 4"
}
```
- DB finds "Class A" timetable ✅
- AI targets "Grade 4" curriculum ✅

### Test Case 3: University
```json
{
  "class_name": "CS101-Section-A",
  "pupils": "Level 100"
}
```
- DB finds "CS101-Section-A" schedule ✅
- AI targets "Level 100" content ✅

---

## 📚 Summary

| Aspect | class_name | pupils |
|--------|------------|--------|
| **Database Query** | ✅ Used | ❌ Not used |
| **AI Prompt** | ✅ Mentioned | ✅ **PRIMARY TARGET** |
| **Storage** | ✅ Used | ✅ Stored for reference |
| **Purpose** | Class identification | Curriculum level |
| **Flexibility** | Any name | Standard levels |

---

## 🚀 Result

**Perfect separation of concerns!**

- ✅ Database uses organizational class names
- ✅ AI uses educational/curriculum levels
- ✅ Both stored for complete context
- ✅ Maximum flexibility for teachers
- ✅ Accurate curriculum targeting

**Best of both worlds! 🎯**
