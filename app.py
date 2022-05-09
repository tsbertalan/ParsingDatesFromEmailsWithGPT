import os

import openai
from flask import Flask, redirect, render_template, request, url_for, Response

from icalendar import Calendar, Event, vText
from datetime import datetime as DateTime
import pytz

from generate_training_JSONL import prepare_prompt, get_stop_tokens
from json import loads
from json.decoder import JSONDecodeError


STOP_TOKENS = get_stop_tokens()

app = Flask(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# with open ('/home/tsbertalan/Dropbox/Projects/Parsing Dates from Emails/event_parsing_GPT_dataset_shorter.txt', 'r') as fp:
#     prompt_template = fp.read()

# After you’ve fine-tuned a model, remember that your prompt has to end with the indicator string `\n====:liamE====` for the model to start generating completions, rather than continuing with the prompt. Make sure to include `stop=["====:desraP===="]` so that the generated texts ends at the expected place.


def get_first_result(result):
    return result.split(STOP_TOKENS[0])[0]

def flatten_dict(d, allowed_atoms=(str, int, float)):
    out = {}
    for k in d.keys():
        v = d[k]
        if isinstance(v, allowed_atoms):
            out[k] = v
        elif isinstance(v, dict):
            out.update(flatten_dict(v, allowed_atoms))
        else:
            out[k] = str(v)
    return out


def compose_results_list_html(response_choices):
    items = []
    for choice in response_choices:
        s = choice['text']
        json_code = get_first_result(s)
        print('JSON from net to parse:', json_code)
#         json_code = '''{
#     "location": "place",
#     "title": "thing",
#     "datetime": {
#         "time": {
#             "hour": 12,
#             "min": 0
#         },
#         "date": {
#             "year": 2022,
#             "month": 6,
#             "day": 15
#         },
#         "tz": "us-east"
#     },
#     "url": "https://zoom.com",
#     "description": "do the thing"
# }'''
        try:
            params = loads(json_code)
            print('Parsed out choice:', params)
            ics_link = url_for('event_ics', **flatten_dict(params))
            print('Create ICS link:', ics_link)
        except JSONDecodeError:
            ics_link = None

        items.append(render_template("result.html", json_code=json_code, ics_link=ics_link))
    return '<ul>' + ('/n'.join(items)) + '</ul>'


def compose_results_page(results_html):
    return render_template("index.html", results=results_html)


@app.route("/", methods=("GET", "POST"))
def index():
    
    if request.method == "POST":
        email = request.form["email"]
        response = openai.Completion.create(
            # engine="text-davinci-002",
            # model='curie:ft-personal-2022-05-06-18-46-42',
            # model='curie:ft-personal-2022-05-06-19-13-43',
            # model='curie:ft-personal-2022-05-06-22-13-43',
            model='curie:ft-personal-2022-05-09-18-23-23',
            prompt=prepare_prompt(email),
            stop=STOP_TOKENS,
            temperature=0.6,
            max_tokens=600,
        )
        return compose_results_page(results_html=compose_results_list_html(response['choices']))
        # return redirect(url_for("index", results=compose_results_list_html(response['choices'])))

    return compose_results_page(results_html="")


@app.route("/event.ics", methods=("GET",))
def event_ics():

    request_args = dict(request.args)
    ical = event_dict_to_ical(**request_args)

    return Response(
        str(ical),
        mimetype='text/plain',
        headers={"Content-Disposition": "attachment;filename=event.ics"}
        )


def event_dict_to_ical(
        location=None,
        title=None,
        year=None,
        month=None,
        day=None,
        hour=None,
        min=0,
        sec=0,
        tz='us-east',
        url=None,
        description='',
    ):
    
    cal = Calendar()
    event = Event()
    if url is not None:
        description = url + '\n\n' + description
    event.add('description', description)
    if title is not None:
        event.add('summary', title)
    if location is None:
        location = url
    if location is not None:
        event.add('location', location)#vText(location)
    # try:
    if tz == 'us-east':
        tz = 'America/New_York'
    dt = DateTime(
        int(year), int(month), int(day), int(hour), int(min), int(sec),
        tzinfo=pytz.timezone(tz)
    )
    event.add('dtstart', dt)
    # except (TypeError, KeyError):
    #     pass
    cal.add_component(event)
    return cal.to_ical().decode('utf-8', 'ignore')



def create_ical_from_parsed(data_s):
    try:
        data = loads(data_s)
    except ValueError:
        return '<emph>Failed to parse JSON to iCal.</emph>'

    return event_dict_to_ical(**data)

