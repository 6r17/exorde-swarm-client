import asyncio
from asyncdb import AsyncDB, AsyncPool

# Define an async function to demonstrate database operations
async def main():
    # Create a connection instance for SQLite using asyncdb
    params = {
        "driver": "sqlite",
        "database": "test.db"
    }
    db = AsyncDB("sqlite", params=params)

    # Create a new table
    async with await db.connection() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS test (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')

    # Insert a row into the table
    async with await db.connection() as conn:
        await conn.execute('INSERT INTO test (name) VALUES (?)', ('Alice',))

    # Query the table
    async with await db.connection() as conn:
        result, error = await conn.query('SELECT * FROM test')
        if error:
            print(f"Query Error: {error}")
        else:
            print("Query Result:", result)

    # Close the database connection
    await db.close()

# Run the async function using asyncio.run if this is the main module
if __name__ == '__main__':
    asyncio.run(main())

