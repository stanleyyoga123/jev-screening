# Screening workspace

React + TypeScript frontend with an editor-style, two-column workspace. Resume
upload/text sits above the questions/job-description editor. The output pane
shows readable outcomes with expandable probability distributions.

## Run locally

Start the backend in one terminal:

```sh
conda activate resume-screening-project
cd apps/api
python -m uvicorn main:app --reload
```

Start the frontend in another terminal (Node 22.18+ recommended):

```sh
cd apps/web
npm install
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to
`http://127.0.0.1:8000`, so no CORS changes or frontend API keys are needed.
To change the backend address, copy `.env.example` to `.env` and edit
`API_PROXY_TARGET` before starting Vite.

## Workflow

1. Upload a text-based PDF (up to 4 MB) or paste resume text. Review/edit extracted text.
2. Paste a Jev question map, or use **Job description → Generate questions**.
   Review the generated JSON. **Check & format** checks all supported question
   types locally; it does not call a model or enforce the stricter role-criteria contract.
3. **Run screening** sends the resume string and question dictionary to `/api/screen`.
4. Expand a result to read the question, outcome description, and probabilities.

Built-in question generation can take a long time. We recommend preparing questions
with ChatGPT or your preferred AI tool when generation is slow. The default provider
timeout is 120 seconds.

To generate questions with ChatGPT or another AI tool, select **Use your own AI**
in the questions pane, then **Copy prompt**. This loads the same prompt used by
the built-in generator from `/api/criteria/prompt` (the backend must be running;
no model call is made). Your current job description is included, or a placeholder
is provided. Paste it into your AI tool, then copy the returned JSON into the
**questions.json** editor and choose **Check & format**. Both a question map and
an object containing a `questions` key are accepted. Review the generated
requirements before screening.

Dark and light themes are available in the top bar. Only the theme preference is
saved locally. Resume, job description, questions, and results stay in React state
and clear on refresh or **Clear session**. Editing inputs clears stale results;
edited job descriptions also clear questions derived from the previous version.
Cancel aborts the browser request, but a provider call already in progress may
still finish and incur cost.

## Result interpretation

For each Choice question, the UI highlights the option with the highest supplied
probability. It presents that probability separately from the model's confidence.
Ties remain marked as ties. Noul shows the more likely yes/no answer, and Score
shows the most likely level alongside the continuous score. Missing confidence is
shown as unavailable rather than invented. Unsupported answers remain visible for
review. Requirement summary counts apply to the four standard role outcomes;
custom questions appear in the result list without being mapped to a hiring score.

Reference formats:
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/primitives/score
- https://docs.typesafe.ai/primitives/noul

## Verify and build

```sh
npm test
npm run build
```

The tests cover question parsing, probability/confidence distinctions, ties,
missing answers, and Choice/Score/Noul results. They do not call paid providers.

`npm run build` creates `dist/`. For deployment, serve those static assets and
reverse-proxy `/api` to FastAPI on the same origin. The development proxy is not
part of the production bundle. `npm run preview` includes the local API proxy.
