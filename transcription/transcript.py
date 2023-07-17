import whisper
import openai

def transcribe():
    model = whisper.load_model("base")
    result = model.transcribe("audio (1).wav")
    transcript = result["text"]
    print(transcript)
    return transcript

def translate():
    transcript = transcribe()
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a translator. Translate these sentences into English."},
            {"role": "user", "content": transcript}
        ]
    )
    print(response['choices'][0]['message']['content'])
    return response['choices'][0]['message']['content']

transcribe()
translate()