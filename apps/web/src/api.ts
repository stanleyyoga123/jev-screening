import { z } from 'zod';

const content = z.union([z.string().regex(/\S/, 'Cannot be blank'), z.record(z.string(), z.unknown()).refine(value => Object.keys(value).length > 0, 'Cannot be empty'), z.array(z.unknown()).min(1)]);
export const questionSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('choice'), instructions: content, criteria: z.record(z.string(), z.unknown()).refine(value => Object.keys(value).length > 0, 'Add at least one option') }).strict(),
  z.object({ type: z.literal('score'), instructions: content, criteria: z.array(z.unknown()).min(1) }).strict(),
  z.object({ type: z.literal('noul'), instructions: content }).strict(),
]);
export const questionsSchema = z.record(z.string().min(1), questionSchema).refine(value => Object.keys(value).length >= 1 && Object.keys(value).length <= 25, 'Use between 1 and 25 questions');
export type Question = z.infer<typeof questionSchema>;
export type Questions = z.infer<typeof questionsSchema>;

export function parseQuestions(text: string): Questions {
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new Error('Questions must be valid JSON. Check for missing quotes, commas, or brackets.'); }
  const parsed = z.union([questionsSchema, z.object({ questions: questionsSchema }).strict()]).safeParse(value);
  if (!parsed.success) throw new Error('Use a map of 1–25 questions, each with a type and instructions. Choice questions need a criteria object; score questions need a criteria list.');
  const result = parsed.data;
  return 'questions' in result && !('type' in result.questions) ? result.questions as Questions : result as Questions;
}

export async function api<T>(path: string, body: object | FormData, schema: z.ZodType<T>, signal: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: 'POST', signal,
      headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error('Cannot reach the API. Check that the backend is running on port 8000.');
  }
  const raw: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = z.object({ detail: z.union([z.string(), z.array(z.object({ loc: z.array(z.union([z.string(), z.number()])), msg: z.string() }))]) }).safeParse(raw);
    const message = detail.success ? (typeof detail.data.detail === 'string' ? detail.data.detail : detail.data.detail.slice(0, 3).map(item => `${item.loc.filter(part => part !== 'body').join('.')}: ${item.msg}`).join('; ')) : 'The API could not complete this request.';
    throw new Error(response.status === 504 ? 'The model took too long. You can try again when ready.' : message);
  }
  const envelope = z.object({ success: z.literal(true), data: schema }).safeParse(raw);
  if (!envelope.success) throw new Error('The API returned an unexpected response. Please check the backend logs.');
  return envelope.data.data;
}

export const screeningSchema = z.object({ answers: z.record(z.string(), z.unknown()), model: z.string().optional() });
