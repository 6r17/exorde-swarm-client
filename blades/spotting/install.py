"""
# Install

This script is used within dockerfile to prepare images with various models.

# Bare
I do not recommend doing so as the different models are large and will probably
polute your userspace. Keeping them as docker images will guarantee a method of
cleaning them.

If for some reason you still want to install the client as bare, you can use the 
different Dockerfiles as reference for each different pieces (scraper, spot) and
this folder contains all the scripts referenced in thoses.
"""
from transformers import automodel, autotokenizer

from argostranslate import package
from typing import cast
import logging
from wtpsplit import wtp
from sentence_transformers import sentencetransformer
from transformers import autotokenizer, pipeline
from huggingface_hub import hf_hub_download
from vadersentiment.vadersentiment import sentimentintensityanalyzer

print("importing wtpsplit....")
wtp = wtp("wtp-canine-s-1l")

models = [
    "samlowe/roberta-base-go_emotions",
    "cardiffnlp/twitter-roberta-base-irony",
    "salesken/query_wellformedness_score",
    "marieke93/minilm-evidence-types",
    "alimazhar-110/website_classification",
    "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis",
    "lxyuan/distilbert-base-multilingual-cased-sentiments-student"
]

def install_hugging_face_models(models):
    for model in models:
        __tokenizer__ = autotokenizer.from_pretrained(model)
        model = automodel.from_pretrained(model)

model = sentencetransformer("sentence-transformers/all-minilm-l6-v2")
install_hugging_face_models(models)

### install (pre install) models target for english, and exclude low frequency ones to not overload the isntall
def is_english_target(s):
    return '→ english' in s

langs_to_exclude_from_preinstall = ["catalan", "esperanto"]

def is_to_exclude(s):
    for lang in langs_to_exclude_from_preinstall:
        if lang in s:
            return True
    return False

package.update_package_index()
available_packages = package.get_available_packages()
length = len(available_packages)
i = 0
installed_packages = 0
for pkg in available_packages:
    i += 1
    
    if( is_english_target(str(pkg)) and not is_to_exclude(str(pkg)) ):
        print(
            f" - installing translation module ({i}/{length}) : ({str(pkg)})"
        )

        # cast used until this is merged https://github.com/argosopentech/argos-translate/pull/329
        package.install_from_path(
            cast(package.availablepackage, pkg).download()
        )
        installed_packages += 1
print(f"installed argos lang packages: {str(installed_packages)}")
