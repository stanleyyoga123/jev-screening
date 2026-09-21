import { z } from 'zod';
import type { Questions } from './api.ts';

const probability = z.number().min(0).max(1);
const distribution = z.record(z.string(), probability);
const answerSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('choice'), choice: z.string(), probabilities: distribution.optional(), confidence: probability.optional() }),
  z.object({ type: z.literal('noul'), noul: probability }),
  z.object({ type: z.literal('score'), score: z.number(), probabilities: distribution.optional(), confidence: probability.optional(), legend: z.record(z.string(), z.string()).optional() }),
]);
export type Outcome = 'meets' | 'partial' | 'does_not_meet' | 'insufficient_evidence' | 'neutral';
export type ResultRow = {
  id: string; title: string; instructions: string; label: string; outcome: Outcome;
  probability: number | null; confidence: number | null; options: { label: string; probability: number; selected: boolean }[];
  description: string; score?: number; unsupported: boolean; tied: boolean;
};

export function readable(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map(readable).filter(Boolean).join(' · ');
  if (typeof value === 'object') return Object.entries(value).map(([key, text]) => `${humanize(key)}: ${readable(text)}`).join(' · ');
  return String(value);
}
export function humanize(value: string): string {
  const names: Record<string, string> = { meets: 'Meets requirement', partial: 'Partially evidenced', does_not_meet: 'Explicit shortfall', insufficient_evidence: 'Not enough evidence' };
  if (names[value]) return names[value];
  const text = value.replace(/^role_/, '').replace(/[_-]/g, ' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function summarize(questions: Questions, answers: Record<string, unknown>): ResultRow[] {
  return Object.entries(questions).map(([id, question]): ResultRow => {
    const base = { id, title: humanize(id), instructions: readable(question.instructions), label: 'Unable to interpret', outcome: 'neutral' as Outcome, probability: null, confidence: null, options: [], description: 'This answer is missing or has an unsupported format. Review the provider response in the backend.', unsupported: true, tied: false };
    const parsed = answerSchema.safeParse(answers[id]);
    if (!parsed.success || parsed.data.type !== question.type) return base;
    const answer = parsed.data;
    if (answer.type === 'noul') {
      const tied = answer.noul === 0.5;
      const yes = answer.noul > 0.5;
      return { ...base, label: tied ? 'Evenly split' : yes ? 'Yes' : 'No', probability: Math.max(answer.noul, 1 - answer.noul), description: tied ? 'The model is equally split between yes and no.' : 'Most likely answer to this question.', options: [{ label: 'Yes', probability: answer.noul, selected: yes || tied }, { label: 'No', probability: 1 - answer.noul, selected: !yes }], unsupported: false, tied };
    }
    const options = Object.entries(answer.probabilities ?? {}).sort((a, b) => b[1] - a[1]);
    const top = options[0];
    const winners = top ? options.filter(([, p]) => p === top[1]).map(([key]) => key) : [];
    const tied = winners.length > 1;
    const key = top?.[0] ?? (answer.type === 'choice' ? answer.choice : '');
    const labelFor = (key: string) => answer.type === 'score' ? ((answer.legend?.[key] ?? (question.type === 'score' ? readable(question.criteria[Number(key)]) : '')) || `Level ${key}`) : humanize(key);
    const label = tied ? `Tied: ${winners.map(labelFor).join(' / ')}` : key ? labelFor(key) : `Score ${answer.type === 'score' ? answer.score.toFixed(2) : 'unavailable'}`;
    const outcomes: Outcome[] = ['meets', 'partial', 'does_not_meet', 'insufficient_evidence'];
    return { ...base, label, outcome: !tied && outcomes.includes(key as Outcome) ? key as Outcome : 'neutral', probability: top?.[1] ?? null, confidence: answer.confidence ?? null,
      options: options.map(([key, probability]) => ({ label: labelFor(key), probability, selected: winners.includes(key) })),
      description: tied ? 'Several options share the highest probability. Review the distribution below.' : question.type === 'choice' ? readable(question.criteria[key]) : 'Most likely level on the supplied scale.',
      score: answer.type === 'score' ? answer.score : undefined, unsupported: false, tied,
    };
  });
}
