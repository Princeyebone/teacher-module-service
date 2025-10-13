# Fixed Foreign Key Violation in Semester Plan Implementation

## Issue Description
We encountered a foreign key constraint violation error when trying to delete substrands that still had content standards referencing them:

```
sqlalchemy.dialects.postgresql.asyncpg.AsyncAdapt_asyncpg_dbapi.IntegrityError: 
<class 'asyncpg.exceptions.ForeignKeyViolationError'>: update or delete on table "substrand" 
violates foreign key constraint "contentstandard_substrand_id_fkey" on table "contentstandard"
DETAIL: Key (id)=(16) is still referenced from table "contentstandard".
```

## Root Cause
The issue was in the deletion order within the `store_ai_response_in_tables` function. Although we had the correct conceptual order (Indicators → ContentStandards → Substrands → Strands), the implementation had a bug:

1. We were trying to delete all substrands for a strand in one bulk operation
2. We were not properly deleting content standards and indicators for each individual substrand
3. This left content standards still referencing substrands that we were trying to delete

## Solution Implemented

### 1. Fixed Deletion Order
We corrected the deletion logic to ensure proper cleanup at each level:

```python
# For each strand, delete associated data in correct order:
for strand in existing_strands:
    # 1. Get all substrands for this strand
    substrands = (await session.execute(
        select(Substrand).where(Substrand.strand_id == strand.id)
    )).scalars().all()
    
    # 2. For each substrand, delete content standards and indicators
    for substrand in substrands:
        # Get all content standards for this substrand
        content_standards = (await session.execute(
            select(ContentStandard).where(ContentStandard.substrand_id == substrand.id)
        )).scalars().all()
        
        # For each content standard, delete indicators first
        for cs in content_standards:
            await session.execute(
                delete(Indicator).where(Indicator.content_standard_id == cs.id)
            )
        
        # Now delete content standards
        await session.execute(
            delete(ContentStandard).where(ContentStandard.substrand_id == substrand.id)
        )
    
    # 3. Now delete substrands one by one
    for substrand in substrands:
        await session.execute(
            delete(Substrand).where(Substrand.id == substrand.id)
        )
    
    # 4. Finally delete the strand
    await session.delete(strand)
```

### 2. Key Improvements
- **Individual Substrand Deletion**: Instead of bulk deleting all substrands for a strand, we now delete them one by one after ensuring their dependent data is cleaned up
- **Proper Cascade Cleanup**: Ensured that for each substrand, we properly delete its content standards and their indicators before deleting the substrand itself
- **Enhanced Logging**: Added detailed debug logging to track the deletion process

## Testing
- ✅ All existing unit tests pass
- ✅ Flat structure parsing tests pass
- ✅ Function import tests pass
- ✅ Data structure validation tests pass

## Benefits
1. **Eliminates Foreign Key Violations**: Proper deletion order prevents constraint violations
2. **Maintains Data Integrity**: Ensures clean state before inserting new data
3. **Better Error Handling**: More robust cleanup process with detailed logging
4. **Improved Reliability**: Reduced risk of database consistency issues

## Files Modified
- `semplan_ground/semplan_back.py`: Fixed deletion order in `store_ai_response_in_tables` function

## Verification
The fix has been verified through:
1. Unit tests
2. Import tests
3. Data structure validation
4. Function signature verification

This fix ensures that the semester plan implementation now properly handles database constraints and maintains data integrity during the cleanup and insertion process.