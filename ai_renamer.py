# ai pdf renamer
# sys.argv[1] <- first command line argument
import pathlib
from google import genai
from google.genai import types, errors
import sys
import os
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch

with open('e:/ai/genai_api_key.txt') as file:
    api_key = file.read().strip()
client = genai.Client(api_key=api_key)

sys_instruct="Answer in the form of a filename [company]_[date]_[invoice number]_[amount].pdf. The company name should be the first word in the text. The date should be in the format YYYY-MM-DD. The invoice number should be a unique identifier. The amount should be a number with two decimal places. If the text does not contain all of these elements, return 'Invalid input'."
0
filepath = pathlib.Path(sys.argv[1])

try:
    response = client.models.generate_content(
        config=types.GenerateContentConfig(system_instruction=sys_instruct),
        model = "gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(
              data=filepath.read_bytes(),
              mime_type="application/pdf",
            ),
            "rename this pdf file to a new name"]
    )
    print(response.text)
    if response.text == "Invalid input":
        print("Invalid input. Please provide a valid PDF file.")
        sys.exit(1)
    confirm = input(f"Do you want to rename the file to {response.text}? (y/n): ")
    if confirm.lower() != 'y':
        print("File renaming cancelled.")
        sys.exit(1)
    try:
        print(f"Renamed file to: {response.text}")
        os.rename(filepath, response.text)
    except Exception as e:
        print(f"Error renaming file: {e}")
        sys.exit(1)
except errors.APIError as e:
    print(f"Error: {e.code} - {e.message}")
    sys.exit(1)
