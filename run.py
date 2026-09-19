from app import create_app
from database import test_database_connection


app = create_app()


if __name__ == "__main__":
    if test_database_connection():
        print("MongoDB connection successful!")
    else:
        print("MongoDB connection failed!")

    app.run(debug=True)