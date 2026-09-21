import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseQuestions } from './api.ts';
import { summarize } from './results.ts';

const questions = { role_python: { type: 'choice' as const, instructions: 'Python experience?', criteria: { meets: 'Documented', partial: 'Some evidence', insufficient_evidence: 'Not established' } } };

test('chooses highest probability, keeping model confidence separate', () => {
  const [row] = summarize(questions, { role_python: { type: 'choice', choice: 'meets', probabilities: { partial: 0.7, meets: 0.2, insufficient_evidence: 0.1 }, confidence: 0.42 } });
  assert.equal(row.outcome, 'partial');
  assert.equal(row.probability, 0.7);
  assert.equal(row.confidence, 0.42);
});

test('never invents missing probability or confidence', () => {
  const [row] = summarize(questions, { role_python: { type: 'choice', choice: 'meets' } });
  assert.equal(row.label, 'Meets requirement');
  assert.equal(row.probability, null);
  assert.equal(row.confidence, null);
});

test('ties remain undecided instead of arbitrarily choosing a requirement outcome', () => {
  const [row] = summarize(questions, { role_python: { type: 'choice', choice: 'meets', probabilities: { meets: 0.5, partial: 0.5 }, confidence: 0 } });
  assert.equal(row.tied, true);
  assert.equal(row.outcome, 'neutral');
  assert.match(row.label, /Tied/);
});

test('noul shows the most likely yes/no answer, including a tie', () => {
  const q = { python: { type: 'noul' as const, instructions: 'Python?' } };
  assert.equal(summarize(q, { python: { type: 'noul', noul: 0.1 } })[0].label, 'No');
  assert.equal(summarize(q, { python: { type: 'noul', noul: 0.1 } })[0].probability, 0.9);
  assert.equal(summarize(q, { python: { type: 'noul', noul: 0.5 } })[0].tied, true);
});

test('score shows the modal level, preserving its distinct weighted score', () => {
  const q = { experience: { type: 'score' as const, instructions: 'Experience?', criteria: ['Basic', 'Intermediate', 'Advanced'] } };
  const [row] = summarize(q, { experience: { type: 'score', score: 1.43, confidence: 0.35, probabilities: { '0': 0, '1': 0.57, '2': 0.43 } } });
  assert.equal(row.label, 'Intermediate');
  assert.equal(row.score, 1.43);
  assert.equal(row.probability, 0.57);
});

test('missing, wrong-type, and invalid answers remain visible for review', () => {
  for (const answer of [undefined, { type: 'choice', choice: 'meets', confidence: 4 }, { type: 'noul', noul: 0.8 }]) {
    const rows = summarize(questions, { role_python: answer });
    assert.equal(rows.length, 1);
    assert.equal(rows[0].unsupported, true);
  }
});

test('accepts question maps and criteria response data without double JSON encoding', () => {
  assert.deepEqual(parseQuestions(JSON.stringify(questions)), questions);
  assert.deepEqual(parseQuestions(JSON.stringify({ questions })), questions);
  assert.throws(() => parseQuestions('"double-encoded string"'));
  assert.throws(() => parseQuestions('{}'));
  assert.throws(() => parseQuestions('{"q":{"type":"choice","instructions":"Pick","criteria":{}}}'));
});
