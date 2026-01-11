# Skill Loading Redesign Analysis

## Design Proposal Analysis

### User's Proposal

**Two tools for skill loading:**

1. **`load_skill`** - Load skill metadata and resource file list (without content)
   - Returns: Skill name, description, SKILL.md body, list of available resources
   - Does NOT include resource file contents

2. **`load_skill_resource`** - Incrementally load resource files into memory's skill cache
   - Loads specific resource files (scripts, references, assets) into memory
   - Content is cached in memory for later use

### Best Practice Analysis

#### ✅ **Advantages (Best Practices)**

1. **Lazy Loading (On-Demand Loading)**
   - ✅ Reduces initial token consumption
   - ✅ LLM only loads what it needs
   - ✅ Better control over context size

2. **Separation of Concerns**
   - ✅ Metadata vs. content separation
   - ✅ Clear tool responsibilities
   - ✅ Better tool design

3. **Incremental Loading**
   - ✅ Load resources only when needed
   - ✅ Avoid loading large files unnecessarily
   - ✅ Better memory management

4. **Caching Strategy**
   - ✅ Loaded resources cached in memory
   - ✅ Avoid repeated loading
   - ✅ Better performance

#### ⚠️ **Potential Concerns**

1. **Complexity**
   - ⚠️ Two tools instead of one
   - ⚠️ LLM needs to understand the relationship
   - ⚠️ More tool calls potentially needed

2. **LLM Understanding**
   - ⚠️ Need clear tool descriptions
   - ⚠️ Need clear prompt guidance
   - ⚠️ LLM must understand when to use which tool

3. **Cache Management**
   - ⚠️ Need to design cache structure in memory
   - ⚠️ Need cache invalidation strategy
   - ⚠️ Need to expose cache to LLM appropriately

#### ✅ **Overall Assessment: GOOD DESIGN**

**Rating: 8.5/10**

This design follows best practices:
- ✅ Lazy loading pattern
- ✅ Separation of concerns
- ✅ Incremental loading
- ✅ Caching strategy

**Recommendations:**
1. ✅ Clear tool descriptions and examples
2. ✅ Clear prompt guidance on when to use each tool
3. ✅ Well-designed cache structure in memory
4. ✅ Cache visibility in memory summary

---

## Design Details

### Tool 1: `load_skill`

**Purpose**: Load skill metadata and resource list (without content)

**Input**:
```python
{
    "name": "long-doc-writer"  # Skill name
}
```

**Output**:
```python
{
    "ok": True,
    "stdout": """
# Skill: long-doc-writer

## Description
Best practices for writing long documents.

## Main Content
[SKILL.md body content]

## Available Resources

### Scripts
- generate_doc.js
- format_doc.py

### References
- style_guide.md
- template_example.md

### Assets
- template.docx
- logo.png

**Note**: Use `load_skill_resource` to load specific resource files.
""",
    "stderr": "",
    "meta": {
        "skill_name": "long-doc-writer",
        "resources": {
            "scripts": ["generate_doc.js", "format_doc.py"],
            "references": ["style_guide.md", "template_example.md"],
            "assets": ["template.docx", "logo.png"]
        }
    }
}
```

**Key Points**:
- ✅ Returns SKILL.md body (main content)
- ✅ Lists available resources (file names only)
- ✅ Does NOT include resource file contents
- ✅ Provides guidance to use `load_skill_resource` for content

### Tool 2: `load_skill_resource`

**Purpose**: Incrementally load resource files into memory's skill cache

**Input**:
```python
{
    "skill_name": "long-doc-writer",
    "resource_type": "scripts",  # "scripts" | "references" | "assets"
    "resource_name": "generate_doc.js"  # File name
}
```

**Output**:
```python
{
    "ok": True,
    "stdout": """
Resource loaded into skill cache.

**Skill**: long-doc-writer
**Resource Type**: scripts
**Resource Name**: generate_doc.js
**Content Length**: 1234 characters

**Note**: This resource is now cached in memory. It will be available in future memory summaries.
""",
    "stderr": "",
    "meta": {
        "skill_name": "long-doc-writer",
        "resource_type": "scripts",
        "resource_name": "generate_doc.js",
        "content_length": 1234,
        "cached": True
    }
}
```

**Key Points**:
- ✅ Loads specific resource file content
- ✅ Caches content in memory
- ✅ Returns confirmation message
- ✅ Does NOT return full content in stdout (to avoid duplication)

---

## Memory Cache Design

### Cache Structure in Memory

**Location**: `state.memory.skill_cache`

**Structure**:
```python
skill_cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
# Format:
# {
#     "skill_name": {
#         "metadata": {
#             "name": "long-doc-writer",
#             "description": "...",
#             "body": "...",  # SKILL.md body
#             "loaded_at_step": 5
#         },
#         "resources": {
#             "scripts": {
#                 "generate_doc.js": {
#                     "content": "...",
#                     "loaded_at_step": 10
#                 },
#                 "format_doc.py": {
#                     "content": "...",
#                     "loaded_at_step": 12
#                 }
#             },
#             "references": {
#                 "style_guide.md": {
#                     "content": "...",
#                     "loaded_at_step": 15
#                 }
#             },
#             "assets": {}  # Assets are usually binary, may not cache content
#         }
#     }
# }
```

### Cache Visibility in Memory Summary

**Strategy**: Show cached skills in Memory Summary

**Format**:
```markdown
## 📚 Loaded Skills (Cached in Memory)

### Skill: long-doc-writer (Loaded at Step 5)
[SKILL.md body content]

**Cached Resources:**
- Scripts: generate_doc.js (Step 10), format_doc.py (Step 12)
- References: style_guide.md (Step 15)

**Available but not loaded:**
- References: template_example.md
- Assets: template.docx, logo.png
```

**Key Points**:
- ✅ Show which skills are cached
- ✅ Show which resources are loaded
- ✅ Show which resources are available but not loaded
- ✅ Guide LLM to load needed resources

---

## Implementation Considerations

### 1. Tool Descriptions

**`load_skill` description**:
```
Load skill metadata and resource list. Returns the skill's main content (SKILL.md body) 
and a list of available resource files (scripts, references, assets) without their contents. 
Use this tool first to explore a skill's capabilities. Then use `load_skill_resource` to 
incrementally load specific resource files when needed.
```

**`load_skill_resource` description**:
```
Load a specific resource file from a skill into memory cache. The resource content will 
be cached and available in future memory summaries. Use this tool after `load_skill` to 
load specific scripts, references, or assets that you need. The content is cached, so 
you don't need to reload it.
```

### 2. Prompt Guidance

**System prompt addition**:
```
## Skill Loading Strategy

When you need to use a skill:

1. **First**: Use `load_skill` to get the skill's main content and see available resources
2. **Then**: Use `load_skill_resource` to load specific resources you need
3. **Note**: Loaded resources are cached in memory and will be available in future summaries

**Example workflow:**
- Step 1: `load_skill(name="long-doc-writer")` → Get main content + resource list
- Step 2: `load_skill_resource(skill_name="long-doc-writer", resource_type="scripts", resource_name="generate_doc.js")` → Load script
- Step 3: Use the cached content in your work
```

### 3. Backward Compatibility

**Note**: User explicitly stated "do not consider backward compatibility"

**Strategy**:
- ✅ Remove old `skill` tool
- ✅ Replace with `load_skill` and `load_skill_resource`
- ✅ Update all references
- ✅ Update tests

### 4. Error Handling

**Cases to handle**:
1. Skill not found
2. Resource not found
3. Resource already cached (idempotent)
4. Invalid resource type
5. Binary files (assets) - may not cache content

---

## Integration with Output Limit Design

### Semantic Type Assignment

**`load_skill`**:
- Output semantic type: `KNOWLEDGE_CONTENT`
- Limit: 60KB (for SKILL.md body + resource list)

**`load_skill_resource`**:
- Output semantic type: `KNOWLEDGE_CONTENT`
- Limit: 60KB (for resource content)
- Note: Content is cached, stdout only contains confirmation

### Memory Summary Integration

**Strategy**:
- Show cached skills in Memory Summary
- Use `KNOWLEDGE_CONTENT` limit for displaying cached content
- Show resource loading status

---

## Migration Plan

### Phase 1: Add Memory Cache Structure
- Add `skill_cache` to `Memory` dataclass
- Implement cache management methods

### Phase 2: Implement New Tools
- Implement `load_skill` tool
- Implement `load_skill_resource` tool
- Update skill loader to support resource loading

### Phase 3: Update Memory Summary
- Add skill cache display to Memory Summary
- Show loaded resources and available resources

### Phase 4: Update Prompts
- Update tool descriptions
- Update system prompt with skill loading strategy
- Update developer prompt with examples

### Phase 5: Remove Old Tool
- Remove `skill` tool
- Update all references
- Update tests

### Phase 6: Testing
- Test skill loading workflow
- Test resource caching
- Test memory summary display
- Test error handling

---

## Summary

### Design Assessment

**Rating: 8.5/10** ✅

**Strengths**:
- ✅ Follows lazy loading best practices
- ✅ Separation of concerns
- ✅ Incremental loading
- ✅ Caching strategy

**Recommendations**:
- ✅ Clear tool descriptions
- ✅ Clear prompt guidance
- ✅ Well-designed cache structure
- ✅ Cache visibility in memory summary

### Integration

This redesign integrates well with the output limit design:
- ✅ Uses semantic types for limits
- ✅ Cached content shown in memory summary
- ✅ Follows same design principles

---

**Analysis Date**: 2026-01-11  
**Version**: 1.0
