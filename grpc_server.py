import grpc
import logging
from config import settings
from sqlmodel import select
from model import TeacherProfile
from database import get_db

import teacher_pb2
import teacher_pb2_grpc

class TeacherServiceServicer(teacher_pb2_grpc.TeacherServiceServicer):
    async def SyncEmail(self, request, context):
        try:
            # 1. Extract metadata to verify Bearer token
            invocation_metadata = dict(context.invocation_metadata())
            auth_header = invocation_metadata.get("authorization", "")
            
            # Remove "Bearer " prefix if present
            token = auth_header.replace("Bearer ", "").strip() if auth_header.startswith("Bearer ") else auth_header.strip()
            
            # Validate token against SERVICE_JWT
            if not token or token != settings.SERVICE_JWT:
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing service token")
            
            # 2. Extract request payload
            old_email = request.old_email
            new_email = request.new_email
            
            if not old_email or not new_email:
                return teacher_pb2.SyncEmailResponse(
                    success=False,
                    message="old_email and new_email are required"
                )
            
            # 3. Database operations
            # Note: We get an asynchronous session from get_db generator
            db_gen = get_db()
            db = await db_gen.__anext__()
            
            try:
                # Query the teacher by the old email
                # NOTE: Assuming TeacherProfile model has an `email` field
                statement = select(TeacherProfile).where(TeacherProfile.email == old_email)
                result = await db.execute(statement)
                teacher = result.scalar_one_or_none()
                
                if not teacher:
                    return teacher_pb2.SyncEmailResponse(
                        success=False,
                        message=f"Teacher with email '{old_email}' not found"
                    )
                
                # Update email
                teacher.email = new_email
                db.add(teacher)
                await db.commit()
                
                return teacher_pb2.SyncEmailResponse(
                    success=True,
                    message=f"Email successfully updated from {old_email} to {new_email}"
                )
            except AttributeError as ae:
                await db.rollback()
                logging.error(f"Attribute error (likely missing email field): {ae}")
                await context.abort(
                    grpc.StatusCode.INTERNAL,
                    f"Database schema error regarding TeacherProfile.email: {ae}"
                )
            except Exception as e:
                await db.rollback()
                logging.error(f"Error updating email: {e}")
                await context.abort(
                    grpc.StatusCode.INTERNAL,
                    f"Internal server error while syncing email: {e}"
                )
            finally:
                await db_gen.aclose()
                
        except Exception as e:
            logging.error(f"Unexpected error in SyncEmail RPC: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, "Unexpected server error")

# Helper function to stand up gRPC independently if desired
async def serve():
    server = grpc.aio.server()
    teacher_pb2_grpc.add_TeacherServiceServicer_to_server(TeacherServiceServicer(), server)
    # Use a port distinct from FastAPI's typical 8000
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    logging.info(f"Starting standalone gRPC server on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(serve())
