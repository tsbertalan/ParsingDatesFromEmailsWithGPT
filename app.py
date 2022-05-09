import os

import openai
from flask import Flask, redirect, render_template, request, url_for, Response

from icalendar import Calendar, Event, Timezone
import x_wr_timezone
from datetime import datetime as DateTime
import pytz

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter

from generate_training_JSONL import prepare_prompt, get_stop_tokens
from json import loads, dumps
from json.decoder import JSONDecodeError


def fuzzy_loads(s, n_recurse=0):
    try:
        return loads(s)
    except JSONDecodeError as e:
        if n_recurse > 5:
            raise e
        # print('Failed to parse JSON:', e)
        se = str(e)
        expecting_comma = "Expecting ',' delimiter" in se
        line_no = se.split('line ')[1].split(' column')[0]
        n_lines = s.count('\n')
        if expecting_comma and abs(int(line_no) - n_lines) <= 1:
            # Try adding a closing "}".
            return fuzzy_loads(s + '}', n_recurse=n_recurse+1)
            
        # print('Line no:', line_no)
        # print('c.v. n lines =', n_lines)
        raise e


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


DEBUG = False

def compose_results_list_html(response_choices):
    items = []
    for choice in response_choices:
        s = choice['text']
        # print('Choice: >>>%s<<<' % s)
        json_code = get_first_result(s)
        # print('JSON from net to parse:', json_code)
        try:
            params = fuzzy_loads(json_code)
            print('Parsed out choice:', params)
            ics_link = url_for('event_ics', **flatten_dict(params))
            print('Create ICS link:', ics_link)
        except JSONDecodeError:
            ics_link = None

        s = highlight(json_code, JsonLexer(), HtmlFormatter(nowrap=False, ))

        # Get corresponding css style and save to file.
        # pygments_css = HtmlFormatter(style='arduino').get_style_defs()
        # import os
        # HERE = os.path.dirname(os.path.realpath(__file__))
        # static_dir = os.path.join(HERE, 'static')
        # with open(os.path.join(static_dir, 'pygments.css'), 'w') as fp:
        #     fp.write(pygments_css)

        # s = '<pre>' + chunked_json_code + '</pre>'

        items.append(render_template("result.html", json_code=s, ics_link=ics_link))
    return '<ul>' + ('/n'.join(items)) + '</ul>'


def compose_results_page(results_html):
    return render_template("index.html", results=results_html)


@app.route("/", methods=("GET", "POST"))
def index():
    
    if request.method == "POST":
        email = request.form["email"]
        if not DEBUG:
            response = openai.Completion.create(
                # engine="text-davinci-002",
                # model='curie:ft-personal-2022-05-06-18-46-42',
                # model='curie:ft-personal-2022-05-06-19-13-43',
                # model='curie:ft-personal-2022-05-06-22-13-43',
                # model='curie:ft-personal-2022-05-09-18-23-23',
                model='curie:ft-personal-2022-05-09-19-50-12',
                prompt=prepare_prompt(email),
                stop=STOP_TOKENS,
                top_p=0.3,
                max_tokens=600,
            )
            print('Response:', response)
        else:
            response = {'choices': [
                {'text': '''{
    "title": "Programming with Commutativity",
    "datetime": {
        "date": {"year": 2022, "month": 5, "day": 9},
        "time": {"hour": 11, "min": 0},
        "tz": "America/New_York"
    },
    "location": "Seminar Room G449 (Patil/Kiva)",
    "url": "https://mit.zoom.us/j/97721705830?pwd=a1VOQVhWTk5hcnc5Rm0xVWFubUtVQT09",
    "description": "There is an ongoing effort to provide programming abstractions that ease the burden of exploiting multicore hardware. Many programming abstractions (e.g., concurrent objects, transactional memory, etc.) simplify matters, but still involve intricate engineering. We argue that some difficulty of multicore programming can be meliorated through a declarative programming style in which programmers directly express the independence of fragments of sequential programs.\\n\\nI will describe a new language paradigm in which programmers write programs in a familiar, sequential manner, with the added ability to explicitly express the conditions under which code fragments sequentially commute. Putting such commutativity conditions into source code offers a new entry point for a compiler to exploit the known connection between commutativity and parallelism. I will discuss semantic implications and how to ensure equivalence between the parallel and sequential semantics.\\n\\nCommutativity conditions (in our and other settings) must be sound or else concurrent execution could be incorrect. I will next describe a series of work (TACAS'18, VMCAI'21) in which we automatically verify and even synthesize commutativity conditions of programs.\\n\\nMore about our language Veracity here: www.veracity-lang.org\\n\\nFor more information please contact: Alexander D Renda, renda@csail.mit.edu"
}'''}
            ]}
        return compose_results_page(results_html=compose_results_list_html(response['choices']))
        # return redirect(url_for("index", results=compose_results_list_html(response['choices'])))

    return compose_results_page(results_html="")


@app.route("/event.ics", methods=("POST",))
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
    tzinfo = pytz.timezone(tz)
    print('Data for dt:', year, month, day, hour, min, sec)
    # https://stackoverflow.com/questions/25668415/why-does-python-new-york-time-zone-display-456-instead-400
    dt = tzinfo.localize(DateTime(
        int(year), int(month), int(day), 
        hour=int(hour), minute=int(min), second=int(sec), microsecond=0,
    ))
    # Convert timezone to UTC.
    dt = dt.astimezone(pytz.utc)
    event.add('dtstart', dt)
    cal.add_component(event)

    # And yet, still include a x-wr-timezone property
    # so Google Calendar will know what timezone to use.
    # https://github.com/collective/icalendar/issues/343
    cal.add('x-wr-timezone', tz)
    new_cal = x_wr_timezone.to_standard(cal)

    # except (TypeError, KeyError):
    #     pass
    return new_cal.to_ical().decode('utf-8', 'ignore')



def create_ical_from_parsed(data_s):
    try:
        data = fuzzy_loads(data_s)
    except ValueError:
        return '<emph>Failed to parse JSON to iCal.</emph>'

    return event_dict_to_ical(**data)

