from flask import Flask, render_template, request, jsonify
import openai
import os
import json
from werkzeug.utils import secure_filename
from PIL import Image
import pytesseract
from dotenv import load_dotenv

app = Flask(__name__)

# Load environment variables from .env file
load_dotenv()

# Set OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure upload folder
app.config['UPLOAD_FOLDER'] = 'uploads/'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Load challenges from JSON
with open('merged_challenges.json', 'r') as f:
    challenges = json.load(f)

# Function to find relevant challenges based on user query
def find_relevant_challenges(query):
    results = []
    for challenge in challenges:
        if query.lower() in challenge['description'].lower():
            results.append({
                "name": challenge['name'],
                "category": challenge['category'],
                "description": challenge['description'],
                "points": challenge.get('points', 'N/A'),
                "files": challenge.get('files', [])
            })
    return results

# Function to extract text from uploaded images
def extract_text_from_image(file_path):
    try:
        text = pytesseract.image_to_string(Image.open(file_path))
        return text
    except Exception as e:
        return f"Error processing image: {e}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/assistant')
def assistant():
    return render_template('assistant.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.form.get("message", "")
        uploaded_files = request.files.getlist("files")

        # Find related challenges
        relevant_challenges = find_relevant_challenges(user_message)

        # Process uploaded files
        file_contexts = []
        for file in uploaded_files:
            if file:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                # Extract text from images
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')): 
                    extracted_text = extract_text_from_image(file_path)
                    file_contexts.append(f"File Name: {filename}\nExtracted Content:\n{extracted_text}")

                # Handle text files
                elif filename.lower().endswith(('.txt', '.md')):
                    with open(file_path, 'r') as f:
                        file_contexts.append(f"File Name: {filename}\nContent:\n{f.read()}")

        # Combine context from challenges and files
        challenge_context = "\n".join(
            [f"Challenge: {ch['name']}\nCategory: {ch['category']}\nDescription: {ch['description']}\nPoints: {ch['points']}" for ch in relevant_challenges]
        )
        file_context = "\n".join(file_contexts)
        combined_context = f"{challenge_context}\n\nAdditional context from files:\n{file_context}"

        # Build OpenAI prompt
        full_prompt = (
            f"You are an expert in CTF challenges. A user has provided the following query:\n\n"
            f"Query: {user_message}\n\n"
            "Here are relevant challenges from the database:\n"
            f"{challenge_context}\n\n"
            "Here is additional context extracted from the uploaded files:\n"
            f"{file_context}\n\n"
            "Based on the above, please provide the following:\n"
            "- Key hints or methodologies for solving the challenges.\n"
            "- If applicable, a step-by-step solution.\n"
            "- Advice on how to approach similar challenges in the future."
        )

        # Send to OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in Capture the Flag (CTF) challenges. Your job is to assist users by analyzing their queries, related challenges, and any uploaded files. Provide clear and structured hints, methodologies, or step-by-step solutions tailored to their needs. Be concise, relevant, and helpful."},
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        gpt_response = response['choices'][0]['message']['content']

        return jsonify({"response": gpt_response})

    except openai.OpenAIError as e:
        return jsonify({"response": f"An error occurred: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
