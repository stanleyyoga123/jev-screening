import { useEffect, useState } from 'react';
import { Check, Copy, LoaderCircle } from 'lucide-react';
import { z } from 'zod';
import { api } from './api';

export function QuestionPrompt({ job }: { job: string }) {
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');
  const text = `${prompt}\n\nJOB DESCRIPTION (source data):\n${job.trim() || '[Paste your job description here]'}`;

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    void api('/criteria/prompt', undefined, z.string().min(1), controller.signal)
      .then(setPrompt)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'Could not load the prompt.');
      });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => { setCopied(false); setCopyError(''); }, [text]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true); setCopyError('');
    } catch {
      setCopyError('Clipboard unavailable. Select the prompt below and copy it manually.');
    }
  }

  return <div className="question-prompt" id="question-prompt">
    <h3>Create questions in your own AI tool</h3>
    <ol>
      <li>Copy this prompt into ChatGPT or another AI tool. {job.trim() ? 'Your current job description is included.' : 'Replace the placeholder at the end with your job description.'}</li>
      <li>Save the JSON response as <code>questions.json</code>, or copy it directly.</li>
      <li>Return to <strong>questions.json</strong>, paste the JSON, then choose <strong>Check & format</strong>. Review the requirements before screening.</li>
    </ol>
    <p>The response can include the outer <code>questions</code> key. Copy only the JSON, without Markdown fences.</p>
    {error ? <div role="alert"><p>{error}</p><button className="secondary-button" onClick={() => setAttempt(attempt + 1)}>Retry loading prompt</button></div>
      : !prompt ? <p role="status"><LoaderCircle size={14} className="spin" /> Loading prompt…</p>
        : <>
          <button className="secondary-button" onClick={() => void copy()}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? 'Copied prompt' : 'Copy prompt'}</button>
          <span className="prompt-feedback" role="status">{copyError || (copied ? 'Ready to paste into your AI tool.' : '')}</span>
          <textarea aria-label="Question generation prompt" readOnly value={text} spellCheck={false} />
        </>}
  </div>;
}
