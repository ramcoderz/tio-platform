import asyncio
from backend.db.session import SessionLocal
from backend.api.router import chat, ChatReq

async def test():
    async with SessionLocal() as db:
        try:
            res = await chat(ChatReq(session_id="test2", message="hello"), db=db)
            print("SUCCESS:", res)
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
