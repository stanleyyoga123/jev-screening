import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent, KeyboardEvent } from 'react';
import { z } from 'zod';
import { ArrowRight, Braces, Check, ChevronDown, CircleAlert, CircleCheck, ClipboardList, FileText, Files, LoaderCircle, Moon, PanelLeft, Play, RotateCcw, ShieldCheck, Sun, Upload, X } from 'lucide-react';
import { api, parseQuestions, questionsSchema, screeningSchema } from './api';
import type { Questions } from './api';
import { summarize } from './results';
import type { ResultRow } from './results';

type Task = 'upload' | 'generate' | 'screen';
type Report = { rows: ResultRow[]; filename: string; time: string; model?: string };
const number = new Intl.NumberFormat('en');
const percent = (value: number) => `${Math.round(value * 100)}%`;

function getTheme(): 'dark' | 'light' {
  try { const stored = localStorage.getItem('jev-theme'); if (stored === 'dark' || stored === 'light') return stored; } catch { /* Theme persistence is optional. */ }
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function Editor({ value, onChange, placeholder, label, disabled, maxLength, mono = true }: {
  value: string; onChange: (value: string) => void; placeholder: string; label: string; disabled?: boolean; maxLength?: number; mono?: boolean;
}) {
  const gutter = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (gutter.current && area.current) gutter.current.style.transform = `translateY(-${area.current.scrollTop}px)`; }, [value]);
  return <div className={`editor ${mono ? 'mono' : 'prose-editor'}`}>
    <div className="gutter" aria-hidden="true"><div ref={gutter}>{Array.from({ length: Math.max(12, value.split('\n').length) }, (_, i) => <div key={i}>{i + 1}</div>)}</div></div>
    <textarea ref={area} aria-label={label} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} spellCheck={!mono} disabled={disabled} maxLength={maxLength}
      onScroll={e => { if (gutter.current) gutter.current.style.transform = `translateY(-${e.currentTarget.scrollTop}px)`; }} />
  </div>;
}

function ResultCard({ row, index }: { row: ResultRow; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const uncertain = row.tied || row.unsupported || row.outcome === 'insufficient_evidence' || (row.confidence !== null && row.confidence < 0.5);
  return <article className={`result-card ${row.outcome}`}>
    <button className="result-toggle" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
      <span className="result-index">{String(index + 1).padStart(2, '0')}</span>
      <span className="result-main"><span className="result-title">{row.title}</span><span className={`outcome ${row.outcome}`}>{row.outcome === 'meets' ? <CircleCheck size={13} /> : uncertain ? <CircleAlert size={13} /> : null}{row.label}</span></span>
      <span className="result-metric"><strong>{row.probability !== null ? percent(row.probability) : '—'}</strong><span>probability</span></span>
      <ChevronDown className={expanded ? 'rotate' : ''} size={15} />
    </button>
    <div className="result-caption"><span>{row.confidence !== null ? `${percent(row.confidence)} model confidence` : 'Confidence not supplied'}{row.score !== undefined ? ` · Score ${row.score.toFixed(2)}` : ''}</span>{uncertain && <span className="review-label">Review needed</span>}</div>
    {expanded && <div className="result-detail">
      <div className="detail-label">QUESTION</div><p>{row.instructions}</p>
      {row.description && <p className="answer-description">{row.description}</p>}
      {row.options.length > 0 && <div className="distribution"><div className="detail-label">ANSWER PROBABILITIES</div>{row.options.map((option, i) => <div className={`distribution-row ${option.selected ? 'selected' : ''}`} key={i}><span>{option.label}</span><div className="bar"><i style={{ width: percent(option.probability) }} /></div><strong>{percent(option.probability)}</strong></div>)}</div>}
    </div>}
  </article>;
}

export default function App() {
  const [theme, setTheme] = useState(getTheme);
  const [resume, setResume] = useState('');
  const [filename, setFilename] = useState('resume.txt');
  const [pasteMode, setPasteMode] = useState(false);
  const [mode, setMode] = useState<'questions' | 'job'>('questions');
  const [questionText, setQuestionText] = useState('');
  const [job, setJob] = useState('');
  const [busy, setBusy] = useState<Task | null>(null);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const questions = useMemo(() => { try { return parseQuestions(questionText); } catch { return null; } }, [questionText]);
  const count = questions ? Object.keys(questions).length : 0;
  const canScreen = !!resume.trim() && resume.length <= 60000 && !!questions && !busy;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#191b20' : '#f3f4f6');
    try { localStorage.setItem('jev-theme', theme); } catch { /* Continue without persisting the preference. */ }
  }, [theme]);
  useEffect(() => () => request.current?.abort(), []);

  function changeTab(event: KeyboardEvent<HTMLButtonElement>) {
    const keys = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const next = event.key === 'Home' ? 'questions' : event.key === 'End' ? 'job' : mode === 'questions' ? 'job' : 'questions';
    setMode(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  function invalidate() { setReport(null); setMessage(null); }
  function editResume(value: string) { setResume(value); invalidate(); }
  function editQuestions(value: string) { setQuestionText(value); invalidate(); }
  function editJob(value: string) { setJob(value); setQuestionText(''); invalidate(); }

  async function execute<T>(task: Task, operation: (signal: AbortSignal) => Promise<T>, onSuccess: (data: T) => void) {
    const controller = new AbortController();
    request.current = controller;
    setBusy(task); setMessage(null);
    try { const data = await operation(controller.signal); if (!controller.signal.aborted) onSuccess(data); }
    catch (error) { if (!controller.signal.aborted) setMessage({ error: true, text: error instanceof Error ? error.message : 'Something went wrong. Please try again.' }); }
    finally { if (request.current === controller) { request.current = null; setBusy(null); } }
  }

  function cancel() { request.current?.abort(); request.current = null; setBusy(null); setMessage({ error: false, text: 'Stopped waiting for this request. An in-flight provider call may still complete.' }); }
  function clear() {
    request.current?.abort(); request.current = null; setBusy(null);
    setResume(''); setFilename('resume.txt'); setPasteMode(false); setQuestionText(''); setJob(''); setReport(null); setMessage(null); setMode('questions');
    if (fileInput.current) fileInput.current.value = '';
  }
  function upload(file: File | undefined) {
    if (!file || busy) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) { setMessage({ error: true, text: 'Choose a PDF file, or paste the resume as text.' }); return; }
    if (file.size > 4_000_000) { setMessage({ error: true, text: 'This PDF is larger than 4 MB. Use a smaller file or paste its text.' }); return; }
    const body = new FormData();
    body.append('file', new File([file], file.name, { type: 'application/pdf' }));
    void execute('upload', signal => api('/documents/parse', body, z.string(), signal), text => {
      setResume(text); setFilename(file.name); setPasteMode(true); setReport(null);
      setMessage(text.length > 60000 ? { error: true, text: 'The extracted resume exceeds 60,000 characters. Shorten it in the editor before screening.' } : text.trim() ? { error: false, text: 'Resume extracted. Review the text before screening.' } : { error: true, text: 'No readable text was found. Paste the resume text instead; scanned PDFs need OCR.' });
    });
  }
  function generate() {
    if (busy || !job.trim()) return;
    void execute('generate', signal => api('/criteria/generate', { job_description: job }, z.object({ questions: questionsSchema }), signal), data => {
      setQuestionText(JSON.stringify(data.questions, null, 2)); setMode('questions'); setReport(null);
      setMessage({ error: false, text: `${Object.keys(data.questions).length} questions generated. Review and edit them before screening.` });
    });
  }
  function formatQuestions() {
    try { const parsed = parseQuestions(questionText); setQuestionText(JSON.stringify(parsed, null, 2)); setMessage({ error: false, text: 'Question structure checked and JSON formatted.' }); }
    catch (error) { setMessage({ error: true, text: (error as Error).message }); }
  }
  function screen() {
    if (!canScreen || !questions) return;
    const snapshot: Questions = questions;
    void execute('screen', signal => api('/screen', { resume, questions: snapshot }, screeningSchema, signal), data => {
      setReport({ rows: summarize(snapshot, data.answers), filename, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), model: data.model });
    });
  }
  const summary = report ? {
    meets: report.rows.filter(row => row.outcome === 'meets').length,
    partial: report.rows.filter(row => row.outcome === 'partial').length,
    gaps: report.rows.filter(row => row.outcome === 'does_not_meet').length,
    unknown: report.rows.filter(row => row.outcome === 'insufficient_evidence' || row.unsupported || row.tied).length,
  } : null;

  return <div className="app-shell">
    <header className="titlebar">
      <a className="brand" href="#workspace" aria-label="Jev screening workspace"><span className="brand-mark"><PanelLeft size={18} /></span><strong>jev</strong><span className="brand-divider">/</span><span className="brand-context">screening workspace</span></a>
      <div className="titlebar-center"><span className="session-dot" />Unsaved session</div>
      <div className="titlebar-actions"><button className="text-button clear-button" onClick={clear} title="Clear all session inputs and results"><RotateCcw size={14} />Clear session</button><div className="theme-switch" aria-label="Color theme"><button aria-label="Light theme" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}><Sun size={15} /></button><button aria-label="Dark theme" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}><Moon size={15} /></button></div></div>
    </header>
    <div className="workspace-bar"><div><span className="eyebrow">WORKSPACE</span><span className="crumb">Resume screening</span></div><span className="workspace-hint">One resume. Your requirements.</span></div>
    {message && <div className={`notice ${message.error ? 'error' : ''}`} role={message.error ? 'alert' : 'status'}>{message.error ? <CircleAlert size={16} /> : <CircleCheck size={16} />}<span>{message.text}</span><button aria-label="Dismiss message" onClick={() => setMessage(null)}><X size={15} /></button></div>}
    <main id="workspace" className="workspace">
      <div className="input-column">
        <section className={`panel resume-panel ${dragging ? 'dragging' : ''}`} aria-label="Resume input" onDragOver={e => { e.preventDefault(); if (!busy) setDragging(true); }} onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false); }} onDrop={e => { e.preventDefault(); setDragging(false); upload(e.dataTransfer.files[0]); }}>
          <div className="panel-tabs"><span className="tab active"><FileText size={15} /><span className="filename">{filename}</span>{resume && <span className="modified-dot" title="Editable text" />}</span><span className="panel-number">01</span></div>
          <div className="panel-toolbar"><span className="panel-caption">RESUME</span><div><input ref={fileInput} type="file" accept="application/pdf,.pdf" hidden onChange={(e: ChangeEvent<HTMLInputElement>) => { upload(e.target.files?.[0]); e.target.value = ''; }} /><button className="text-button" disabled={!!busy} onClick={() => fileInput.current?.click()}><Upload size={13} />{resume ? 'Replace PDF' : 'Upload PDF'}</button></div></div>
          {!pasteMode && !resume ? <div className="upload-empty">
            <button className="dropzone" disabled={!!busy} onClick={() => fileInput.current?.click()}>
              <span className="document-icon">{busy === 'upload' ? <LoaderCircle className="spin" size={26} /> : <FileText size={26} />}</span>
              <strong>{busy === 'upload' ? 'Extracting resume…' : dragging ? 'Drop your PDF here' : 'Drop a resume here'}</strong>
              <span>or <span className="inline-link">browse files</span> to upload</span><small>Text-based PDF · up to 4 MB</small>
            </button><button className="text-button paste-button" disabled={!!busy} onClick={() => setPasteMode(true)}>Paste resume text <ArrowRight size={13} /></button>
          </div> : <Editor value={resume} onChange={editResume} label="Resume text" placeholder="Paste the resume here, or upload a PDF above…" disabled={!!busy} maxLength={60000} mono={false} />}
          <div className="panel-status"><span>{resume ? <><Check size={12} />Editable text</> : 'Waiting for resume'}</span><span>{number.format(resume.length)} / 60,000 characters</span></div>
        </section>
        <section className="panel questions-panel" aria-label="Questions and job description">
          <div className="panel-tabs input-tabs" role="tablist" aria-label="Question source"><button className={`tab ${mode === 'questions' ? 'active' : ''}`} id="tab-questions" role="tab" tabIndex={mode === 'questions' ? 0 : -1} onKeyDown={changeTab} aria-selected={mode === 'questions'} aria-controls="criteria-editor" disabled={!!busy} onClick={() => setMode('questions')}><Braces size={15} />questions.json{count > 0 && <span className="tab-count">{count}</span>}</button><button className={`tab ${mode === 'job' ? 'active' : ''}`} id="tab-job" role="tab" tabIndex={mode === 'job' ? 0 : -1} onKeyDown={changeTab} aria-selected={mode === 'job'} aria-controls="criteria-editor" disabled={!!busy} onClick={() => setMode('job')}><FileText size={14} />Job description</button><span className="panel-number">02</span></div>
          <div className="panel-toolbar"><span className="panel-caption">{mode === 'questions' ? 'SCREENING QUESTIONS' : 'GENERATE REQUIREMENTS'}</span>{mode === 'questions' ? <button className="text-button" disabled={!!busy || !questionText.trim()} onClick={formatQuestions}><Braces size={13} />Check & format</button> : <span className="subtle-label">GLM generator</span>}</div>
          <div className="criteria-editor" id="criteria-editor" role="tabpanel" aria-labelledby={`tab-${mode}`} aria-label={mode === 'questions' ? 'Questions JSON' : 'Job description'}>
            <Editor value={mode === 'questions' ? questionText : job} onChange={mode === 'questions' ? editQuestions : editJob} label={mode === 'questions' ? 'Questions JSON' : 'Job description text'} disabled={!!busy} maxLength={mode === 'job' ? 30000 : 100000} mono={mode === 'questions'} placeholder={mode === 'questions' ? '{\n  "role_python": {\n    "type": "noul",\n    "instructions": "Is Python experience documented?"\n  }\n}\n\nPaste your question map here, or use the\nJob description tab to generate questions.' : 'Paste the job description here.\n\nInclude the role’s skills, experience, and qualifications. The generator will turn these into editable screening questions.'} />
          </div>
          {mode === 'job' && <div className="generation-toolbar"><span>Review generated questions before screening.</span><button className="secondary-button" disabled={!!busy || !job.trim()} onClick={generate}>{busy === 'generate' ? <LoaderCircle className="spin" size={14} /> : <Braces size={14} />}{busy === 'generate' ? 'Generating…' : 'Generate questions'}<ArrowRight size={13} /></button></div>}
          <div className="panel-status"><span>{mode === 'questions' ? count ? <><Check size={12} />{count} questions ready</> : questionText ? <><CircleAlert size={12} />Check question format</> : 'No questions yet' : 'Job description → questions'}</span><span>{mode === 'questions' ? 'JSON' : `${number.format(job.length)} / 30,000 characters`}</span></div>
        </section>
      </div>
      <section className="panel output-panel" aria-label="Screening output">
        <div className="panel-tabs"><span className="tab active"><ClipboardList size={15} />screening.report</span><span className="panel-number">OUTPUT</span></div>
        <div className="report-toolbar"><div><span className="panel-caption">EVIDENCE REVIEW</span><h1>Screening report</h1></div><button className="primary-button" onClick={screen} disabled={!canScreen} title={!resume.trim() ? 'Add a resume first' : resume.length > 60000 ? 'Shorten the resume to 60,000 characters' : !questions ? 'Add valid questions first' : 'Evaluate the resume against your questions'}>{busy === 'screen' ? <LoaderCircle className="spin" size={15} /> : <Play size={14} fill="currentColor" />}{busy === 'screen' ? 'Screening…' : 'Run screening'}</button></div>
        <div className="report-scroll" aria-live="polite" aria-busy={busy === 'screen'}>
          {busy === 'screen' ? <div className="report-empty loading"><span className="empty-symbol"><LoaderCircle size={32} className="spin" /></span><h2>Reading the evidence</h2><p>Evaluating {count} questions against your resume.</p><div className="loading-line" /><button className="text-button" onClick={cancel}>Cancel request</button></div> : report && summary ? <div className="report-content">
            <div className="report-context"><span><CircleCheck size={14} />Screening complete</span><span>{report.time}</span></div>
            {report.rows.some(row => row.outcome !== 'neutral') && <div className="summary-grid"><div><strong>{summary.meets}</strong><span>Meets</span><i className="summary-marker meets" /></div><div><strong>{summary.partial}</strong><span>Partial</span><i className="summary-marker partial" /></div><div><strong>{summary.gaps}</strong><span>Shortfall</span><i className="summary-marker does_not_meet" /></div><div><strong>{summary.unknown}</strong><span>Unclear</span><i className="summary-marker insufficient_evidence" /></div></div>}
            <div className="results-heading"><span>{report.rows.length} question{report.rows.length !== 1 ? 's' : ''}</span><span>Most likely outcome</span></div>
            <div className="results-list">{report.rows.map((row, index) => <ResultCard key={`${report.time}-${row.id}`} row={row} index={index} />)}</div>
            <div className="review-note"><ShieldCheck size={17} /><p>Review evidence, not just percentages. Missing information does not establish a shortfall. Results support your review, not a hiring decision.</p></div>
            <div className="report-source"><FileText size={12} /><span>{report.filename}</span>{report.model && <span className="model-name">{report.model}</span>}</div>
          </div> : <div className="report-empty"><span className="empty-symbol"><ClipboardList size={30} /></span><span className="eyebrow">YOUR NEXT REVIEW STARTS HERE</span><h2>From resume to evidence.</h2><p>Add a resume and your requirements.<br />We’ll put the most likely answers here.</p><div className="readiness-list"><div className={resume.trim() ? 'ready' : ''}><span>{resume.trim() ? <Check size={13} /> : '1'}</span><p>Add a resume</p><small>{resume.trim() ? 'Ready' : 'PDF or text'}</small></div><div className={count > 0 ? 'ready' : ''}><span>{count > 0 ? <Check size={13} /> : '2'}</span><p>Define your questions</p><small>{count > 0 ? `${count} ready` : 'Or generate from a JD'}</small></div><div><span>3</span><p>Run a screening</p><small>Review each outcome</small></div></div></div>}
        </div>
        <div className="panel-status output-status"><span><ShieldCheck size={12} />For human review</span><span>{report ? `${report.rows.length} results` : 'No screening yet'}</span></div>
      </section>
    </main>
    <footer className="statusbar"><span><Files size={13} />{busy ? busy === 'upload' ? 'Extracting PDF…' : busy === 'generate' ? 'Generating questions…' : 'Screening resume…' : 'Workspace ready'}{busy && <button onClick={cancel}>Cancel</button>}</span><span className="footer-privacy">Inputs stay in this session · Sent to providers when you run</span><span>{theme === 'dark' ? <Moon size={12} /> : <Sun size={12} />} {theme === 'dark' ? 'Dark' : 'Light'}</span></footer>
  </div>;
}
