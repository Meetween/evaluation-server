import argparse
import json
import os, sys
from pathlib import Path

import groq
from tqdm import tqdm

debugFlag = False
groq_client = groq.Groq(
    api_key=os.environ["GROQ_API_KEY"], timeout=5.0, max_retries=6
)

def debug(msg):
    if debugFlag:
        print(f'{msg}', file=sys.stderr)

def evaluate_answer(context, question, answer):
    try:
        chat_completion = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that evaluates answers to "
                        "questions given a certain context. You will be given "
                        "inputs of the form: \n"
                        "Context: <CONTEXT>\n"
                        "Question: <QUESTION>\n"
                        "Answer: <ANSWER>\n"
                        "Your task is to determine if the given answer is correct "
                        "or not, assuming the correct answer is contained in the "
                        "context.\n"
                        "Your response should be formatted as a JSON string "
                        "having the following structure: \n"
                        "{\"correct_answer\": <true/false>, \"rationale\": <RATIONALE>}\n"
                        "where 'rationale' must be a string explaining why the "
                        "answer is correct or incorrect. If you need to include "
                        "double quote characters (\") in the 'rationale' string, "
                        "you must escape them with a backslash (\\). For example, "
                        "if you want to include the string \"Hello, World!\", you "
                        "should write it as \\\"Hello, World!\\\"."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Context: \"{context}\"\n"
                        f"Question: \"{question}\"\n"
                        f"Answer: \"{answer}\""
                    ),
                },
            ],
            seed=42,
        )
    except Exception as e:
        debug(f'evaluate_answer: exception {e}.')
        return None, "Low level error", None
    output = chat_completion.choices[0].message.content
    try:
        output_json = json.loads(output)
    except json.JSONDecodeError:
        out2 = output.encode('unicode_escape').decode('ASCII')
        try:
            output_json = json.loads(out2)
        except json.JSONDecodeError:
            return None, "Invalid JSON string", output + out2
        debug("  out2 is OK")
    if not isinstance(output_json["correct_answer"], bool):
        debug("Invalid correct_answer value.")
        return None, "Invalid correct_answer value", output
    is_correct = output_json["correct_answer"]
    rationale = output_json["rationale"]
    return is_correct, rationale, output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-r", "--reference-file", type=Path)
    parser.add_argument("-p", "--prediction-file", type=Path)
    parser.add_argument("-o", "--output-file", type=Path)
    parser.add_argument("-s", "--save-step", type=int, help="default 1000")
    args = parser.parse_args()
    if args.debug:
        global debugFlag
        debugFlag = True

    dataset = json.loads(args.reference_file.read_text())["data"]
    predictions = json.loads(args.prediction_file.read_text())
    evaluation_outcome = {}
    if args.output_file.exists():
        evaluation_outcome = json.loads(args.output_file.read_text())
    debug(f'initialized evaluation_outcome {len(evaluation_outcome)}')

    doneCnt  = 0
    predTodo = len(predictions)
    saveStep = 200
    cntTrue  = 0
    cntFalse = 0
    cntNone  = 0
    cntSkip  = 0
    if args.save_step:
       saveStep = args.save_step
    args.output_file.parent.mkdir(exist_ok=True, parents=True)
    for article in dataset:
        debug(f'scan paragraph {len(article["paragraphs"])}')
        for paragraph in article["paragraphs"]:
            debug(f'scan qas {len(paragraph["qas"])}')
            if len(paragraph["qas"]) == 0:
                continue
            context = paragraph["context"]
            for qa in paragraph["qas"]:
                question_id = qa["id"]
                if question_id not in predictions:
                    # SQuAD is a superset of Spoken-SQuAD, so some
                    # questions in the dataset may not be present in the
                    # predictions.
                    continue
                if question_id in evaluation_outcome:
                    debug(f'already evaluated {question_id}')
                    continue
                question = qa["question"]
                is_correct, rationale, raw_api_output = evaluate_answer(
                    context=context,
                    question=question,
                    answer=predictions[question_id],
                )
                if raw_api_output is None:
                    debug(f'skipping {question_id}: reason {rationale}')
                    cntSkip += 1
                    continue
                evaluation_outcome[question_id] = {
                   "is_correct": is_correct
                }
                if is_correct is None:
                    debug(f'None is_correct {question_id}: reason {rationale}, raw_api_output {raw_api_output}')
                    evaluation_outcome[question_id]["raw_api_output"] = raw_api_output
                    evaluation_outcome[question_id]["error"] = rationale
                doneCnt += 1
                # save every saveStep
                if ((doneCnt + cntSkip) % saveStep) == 1:
                    args.output_file.write_text(json.dumps(evaluation_outcome, ensure_ascii=False, indent=2))
                    debug(f'saved {doneCnt + cntSkip} {len(evaluation_outcome)}')

    args.output_file.write_text(
        json.dumps(evaluation_outcome, ensure_ascii=False, indent=2)
    )
    debug(f'saved {doneCnt} {len(evaluation_outcome)}')
    for id in evaluation_outcome:
        is_correct = evaluation_outcome[id]["is_correct"]
        if is_correct is None:
            cntNone += 1
        elif is_correct:
            cntTrue += 1
        else:
            cntFalse += 1
    debug(f'final stats: predTodo {predTodo}, doneCnt {doneCnt}, cntTrue {cntTrue}, cntFalse {cntFalse}, cntNone {cntNone}, cntSkip {cntSkip}')
    accuracy = cntTrue / (cntTrue + cntFalse + cntNone + cntSkip) * 100
    accStr = f'{accuracy:.2f}'
    inQStr = f'{predTodo}'
    evQStr = f'{cntTrue + cntFalse}'
    res = {"accuracy":  accStr, 
           "input_questions": inQStr,
           "evaluated_questions": evQStr}
    print(res)
    

if __name__ == "__main__":
    main()
