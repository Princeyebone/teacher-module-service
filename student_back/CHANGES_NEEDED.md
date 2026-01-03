# Summary of changes needed for student_support_generator.py

## 1. Remove subject from image prompts (line 353)
Change:
```python
f"Educational diagram explaining {topic} in {subject}, clean simple illustration",
```
To:
```python
f"Educational diagram explaining {topic}, clean simple illustration",
```

## 2. Add notes parser function (after line 380, before _build_support_pack_slides)
Add the _parse_notes_into_slides function from student_pack_generator.py

## 3. Update _build_support_pack_slides function (around line 450-461)
Replace the single notes slide:
```python
# === 4. Notes Slides ===
if notes_html:
    slides.append({
        "id": f"slide-{slide_num}",
        "type": "notes",
        "layout": "notes",
        "content": {
            "title": "Your Learning Notes",
            "html_content": notes_html
        }
    })
    slide_num += 1
```

With parsed notes slides:
```python
# === 4. Notes Slides (parsed into multiple slides) ===
if notes_html:
    notes_slides = _parse_notes_into_slides(notes_html, slide_num)
    slides.extend(notes_slides)
    slide_num += len(notes_slides)
```

## 4. Remove subject from title slide subtitle (line 407)
Change:
```python
"subtitle": f"Prepared for {student_name} - {subject} ({class_name})"
```
To:
```python
"subtitle": f"Prepared for {student_name} ({class_name})"
```

These changes will:
- Remove subject references from AI prompts
- Parse notes into multiple structured slides like student lesson pack
- Use notes_section type for better structure
