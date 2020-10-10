import os, logging, io, json, warnings
logging.basicConfig(level="INFO")
warnings.filterwarnings('ignore')

import sys
python = sys.executable

# In your environment run:
os.system("python -m spacy download es_core_news_md")
os.system("python -m spacy link es_core_news_md es --force")

import rasa
from rasa.model import get_model
from rasa.shared.nlu.training_data.loading import load_data
from rasa.shared.core.slots import Slot, TextSlot
from rasa.shared.core.domain import Domain
from rasa.nlu import config, utils
from rasa.nlu.components import ComponentBuilder
from rasa.nlu.config import RasaNLUModelConfig
from rasa.nlu.model import Interpreter, Trainer, TrainingData
from rasa.nlu.components import Component
from rasa.nlu.tokenizers.tokenizer import Token
from rasa.utils.tensorflow.constants import ENTITY_RECOGNITION

import spacy

#spacy_parser = spacy.load('es_core_news_md')
#nlp = spacy.load('es')

# loading the nlu training samples
training_data = load_data("data/nlu/nlu.yml")

# trainer to educate our pipeline
trainer = Trainer(config.load("config.yml"))

# train the model!
interpreter = trainer.train(training_data)

# store it for future use
model_directory = trainer.persist("./models/nlu", fixed_model_name="current")

#Starting the Bot
from rasa.core.agent import Agent
from rasa.core.utils import EndpointConfig

action_endpoint = EndpointConfig(url="http://0.0.0.0:5055/webhook")
agent = Agent.load('models/dialogue', interpreter=model_directory, action_endpoint=action_endpoint)

#!git clone https://github.com/NVIDIA/tacotron2.git
#!git clone https://github.com/DeepLearningExamples/CUDA-Optimized/FastSpeech.git

from tacotron2.hparams import create_hparams
from tacotron2.model import Tacotron2
from tacotron2.stft import STFT
from tacotron2.audio_processing import griffin_lim
from tacotron2.train import load_model
from fastspeech.text_norm import text_to_sequence
from tacotron2.waveglow.mel2samp import files_to_list, MAX_WAV_VALUE
from fastspeech.inferencer.denoiser import Denoiser
import numpy as np
import torch

def synthesize(text, voice, sigma=0.6, denoiser_strength=0.05, is_fp16=False):

    hparams = create_hparams()
    hparams.sampling_rate = 22050

    if voice == "papaito":
        voice_model = "nvidia_tacotron2_papaito_300"
    elif voice == "constantino":
        voice_model = "tacotron2_Constantino_600"
    elif voice == "orador":
        voice_model = "checkpoint_tacotron2_29000_es"
    
    checkpoint_path = "/home/debian/workspace/models/" + voice_model
        
    model = load_model(hparams)
    model.load_state_dict(torch.load(checkpoint_path)['state_dict'])
    _ = model.cuda().eval().half()

    waveglow_path = '/home/debian/workspace/models/waveglow_256channels_ljs_v2.pt'
    waveglow = torch.load(waveglow_path)['model']
    _ = waveglow.cuda().eval().half()
    denoiser = Denoiser(waveglow)

    #text="¡Cágate lorito!"
    #with open(filelist_path, encoding='utf-8', mode='r') as f:
    #    text = f.read()

    sequence = np.array(text_to_sequence(text, ['english_cleaners']))[None, :]
    sequence = torch.autograd.Variable(
        torch.from_numpy(sequence)).cuda().long()

    mel_outputs, mel_outputs_postnet, _, alignments = model.inference(sequence)
    #mel = torch.unsqueeze(mel, 0)
    mel = mel_outputs.half() if is_fp16 else mel_outputs
    audio = np.array([])
    with torch.no_grad():
        audio = waveglow.infer(mel, sigma=sigma)
        if denoiser_strength > 0:
             audio = denoiser(audio, denoiser_strength)
        audio = audio * MAX_WAV_VALUE
        audio = audio.squeeze()
        audio = audio.cpu().numpy()
        audio = audio.astype('int16')
    
    return audio, hparams.sampling_rate

import sounddevice as sd
import asyncio
from sty import fg, bg, ef, rs
from wtforms import Form, StringField, validators

class InputForm(Form):
    a = StringField(
        label='Texto', default=u'',
        validators=[validators.InputRequired()])

async def play_buffer(buffer, samplerate):
    loop = asyncio.get_event_loop()
    event = asyncio.Event()
    idx = 0

    def callback(outdata, frame_count, time_info, status):
        nonlocal idx
        if status:
            print(status)
        remainder = len(buffer) - idx
        if remainder == 0:
            loop.call_soon_threadsafe(event.set)
            raise sd.CallbackStop
        valid_frames = frame_count if remainder >= frame_count else remainder
        outdata[:valid_frames] = buffer[idx:idx + valid_frames]
        outdata[valid_frames:] = 0
        idx += valid_frames

    stream = sd.OutputStream(callback=callback, dtype=buffer.dtype,
                    channels=buffer.shape[1], samplerate=samplerate)
    with stream:
        await event.wait()

from flask import Flask, render_template, request

app = Flask(__name__)
@app.route('/', methods = ['GET', 'POST'])

async def index():

    #while True:
        form = InputForm(request.form)
        if request.method == 'POST' and form.validate():

            if form.a.data == 'quieto parao':
                #break
                return('')
                sys.exit(0)
            # Return RASA bot response
            responses = agent.handle_text(form.a.data)
            for response in responses:
                to_synth = response["text"]
                #to_synth = "Esto es una prueba para ver si funciona"
                result = to_synth
                response_file = open('response.txt','w') 
                response_file.write(to_synth)

                # Synthesize bot voice with desired pretrained NVIDIA Tacotron2 spanish fine-tuned voice model
                #voice, sr = synthesize(to_synth, "orador")

                #Stream bot voice through flask HTTP server
                #stream = sd.OutputStream(dtype='int16', channels=1, samplerate=22050.0)
                #stream.start()
                #stream.write(voice)
                #stream.close()
                #sd.play(voice, sr)

                response_file.close()
        else:
            result = None

        return await render_template('chitchat.html', form=form, result=result)
