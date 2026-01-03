# Student Lesson Pack - Quick Reference

## 🚀 Quick Start

### Get Student Pack
```javascript
const pack = await fetch(
  '/api/teacher/student-packs?subject=Physics&class_name=Class%2011A',
  { headers: { 'Authorization': `Bearer ${token}` } }
).then(r => r.json());
```

### Use Audio
```javascript
audioPlayer.src = pack.podcast_audio_signed_url;
```

### Update Pack
```javascript
await fetch(`/api/teacher/student-packs/${packId}`, {
  method: 'PUT',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    simplified_notes: '<h2>Updated Notes</h2>'
  })
});
```

---

## 📋 Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/student-packs?subject=X&class_name=Y` | Get pack |
| GET | `/student-packs/{id}` | Get by ID |
| GET | `/student-packs/by-session/{id}` | Get by session |
| GET | `/student-packs/list` | List all |
| PUT | `/student-packs/{id}` | Update |
| GET | `/student-packs/{id}/audio` | Get signed URL |

---

## 📦 Pack Structure

```json
{
  "id": "uuid",
  "status": "completed",
  "podcast_audio_signed_url": "https://...",
  "slides": [
    { "type": "title", "content": {...} },
    { "type": "notes", "content": {...} },
    { "type": "video_resources", "content": {...} },
    { "type": "podcast", "content": {...} },
    { "type": "assessment_mcq", "content": {...} },
    { "type": "assessment_essay", "content": {...} },
    { "type": "answer_key_mcq", "content": {...} },
    { "type": "answer_key_essay", "content": {...} }
  ],
  "summary": {
    "total_slides": 8,
    "video_count": 5,
    "mcq_count": 15,
    "essay_count": 5,
    "podcast_duration_ms": 668029
  }
}
```

---

## 🎨 Slide Types

| Type | Description | Key Fields |
|------|-------------|------------|
| `title` | Title slide | `title`, `subtitle` |
| `notes` | Lesson notes | `html_content` |
| `video_resources` | YouTube videos | `videos[]` |
| `podcast` | Audio player | `audio_url`, `duration_ms` |
| `assessment_mcq` | MCQ questions | `questions[]` (no answers) |
| `assessment_essay` | Essay questions | `questions[]` (no key_points) |
| `answer_key_mcq` | MCQ answers | `answers[]` with explanations |
| `answer_key_essay` | Essay answers | `answers[]` with key_points |

---

## 🔐 Signed URLs

### Why?
- Audio files are private in GCS
- Signed URLs provide temporary access (60 min default)

### Usage
```javascript
// Already included in pack response
audioPlayer.src = pack.podcast_audio_signed_url;

// Or get fresh URL
const { signed_url } = await fetch(
  `/api/teacher/student-packs/${packId}/audio?expiration_minutes=120`
).then(r => r.json());
```

### Refresh Before Expiration
```javascript
setTimeout(() => {
  refreshAudioUrl(packId);
}, 50 * 60 * 1000); // 50 minutes
```

---

## 📁 Storage Structure

```
student_packs/
  └── {teacher_id}/
      └── {session_id}/
          └── podcast.mp3
```

Example:
```
student_packs/7bed2b69-8000-4b36-8e91-7fe0b70c9d82/1618/podcast.mp3
```

---

## ⚡ Status Values

| Status | Meaning | Action |
|--------|---------|--------|
| `pending` | Queued | Show "Queued..." |
| `processing` | Generating | Show "Generating..." |
| `completed` | Ready | Display pack |
| `failed` | Error | Show error message |

---

## 🎯 Common Patterns

### Load and Display
```javascript
const pack = await loadPack(subject, className);
if (!pack) {
  return <div>No pack available</div>;
}
return <PackViewer pack={pack} />;
```

### Handle Loading
```javascript
if (pack.status === 'processing') {
  return <div>Generating pack... <Spinner /></div>;
}
```

### Render Slides
```javascript
pack.slides.map(slide => (
  <SlideComponent key={slide.id} slide={slide} />
))
```

### Play Audio
```javascript
<audio controls src={pack.podcast_audio_signed_url} />
```

---

## 🛠️ Error Handling

```javascript
try {
  const pack = await loadPack(subject, className);
} catch (error) {
  if (error.status === 404) {
    showMessage('Pack not found');
  } else if (error.status === 401) {
    redirectToLogin();
  } else {
    showError('Failed to load pack');
  }
}
```

---

## 📊 Summary Fields

```javascript
const {
  total_slides,      // 8
  has_notes,         // true
  video_count,       // 5
  has_podcast,       // true
  podcast_duration_ms, // 668029 (~11 min)
  mcq_count,         // 15
  essay_count        // 5
} = pack.summary;
```

---

## 🔄 Update Examples

### Update Notes
```javascript
await updatePack(packId, {
  simplified_notes: '<h2>New Notes</h2>'
});
```

### Update Videos
```javascript
await updatePack(packId, {
  video_resources: [
    {
      title: "New Video",
      url: "https://youtube.com/...",
      thumbnail: "https://...",
      type: "video"
    }
  ]
});
```

### Update Entire Pack
```javascript
await updatePack(packId, {
  content_json: {
    ...pack.content_json,
    slides: modifiedSlides
  }
});
```

---

## 📚 Full Documentation

- **API Reference**: `docs/STUDENT_LESSON_PACK_API.md`
- **Implementation Summary**: `docs/STUDENT_PACK_IMPLEMENTATION_SUMMARY.md`
- **Swagger UI**: `https://your-domain.com/api/docs`

---

## ✅ Checklist for Frontend

- [ ] Fetch pack by subject/class
- [ ] Display all slide types
- [ ] Implement audio player
- [ ] Handle signed URL expiration
- [ ] Show loading states
- [ ] Handle errors gracefully
- [ ] Implement edit mode
- [ ] Add video thumbnails
- [ ] Show/hide answer keys
- [ ] Test with different pack statuses

---

## 🎓 Example: Complete Component

```jsx
function StudentPack({ subject, className }) {
  const [pack, setPack] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/teacher/student-packs?subject=${subject}&class_name=${className}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    .then(r => r.json())
    .then(setPack)
    .finally(() => setLoading(false));
  }, [subject, className]);

  if (loading) return <Spinner />;
  if (!pack) return <div>No pack available</div>;

  return (
    <div>
      <h1>{pack.topic}</h1>
      {pack.slides.map(slide => (
        <Slide key={slide.id} data={slide} />
      ))}
    </div>
  );
}
```

---

## 🚨 Important Notes

1. **Signed URLs expire after 60 minutes** - Implement refresh logic for long sessions
2. **Check status before displaying** - Handle `processing` and `failed` states
3. **Answer keys are separate slides** - Don't show immediately to students
4. **Use structured format** - The `slides` array is the recommended format
5. **Audio is MP3** - Compatible with all browsers

---

## 💡 Tips

- Cache packs locally to reduce API calls
- Preload audio for better UX
- Show video thumbnails for faster loading
- Implement keyboard shortcuts for slide navigation
- Add download button for offline access
- Track which slides students have viewed

---

**Ready to integrate? Start with the API documentation!** 📖
