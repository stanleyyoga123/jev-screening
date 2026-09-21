import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.application import create_app
from domains.criteria.model import GeneratedCriteria
from domains.screening.schema import ScreeningRequest


QUESTION = {
    "type": "choice",
    "instructions": "Does the resume document professional Python experience?",
    "criteria": {
        "meets": "Professional Python experience is documented.",
        "partial": "Some relevant experience is documented.",
        "does_not_meet": "Explicit evidence establishes a shortfall.",
        "insufficient_evidence": "The requirement is not established.",
    },
}


class CriteriaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(patch('domains.criteria.factory.Settings', side_effect=AssertionError('Validation must not load credentials')))
        self.enterContext(patch('integrations.generator.httpx.AsyncClient', side_effect=AssertionError('Validation must not create an HTTP client')))
        self.client = self.enterContext(TestClient(create_app()))

    def test_accepts_generated_questions_as_object_or_string(self) -> None:
        questions = {'role_python': QUESTION}
        for value in (questions, json.dumps(questions)):
            with self.subTest(input_type=type(value).__name__):
                response = self.client.post('/api/criteria/validate', json={'questions': value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'success': True, 'data': {'questions': questions}})
                GeneratedCriteria.model_validate(response.json()['data'])
                ScreeningRequest(resume='Python developer', questions=json.dumps(response.json()['data']['questions']))

    def test_normalizes_default_question_type(self) -> None:
        question = {key: value for key, value in QUESTION.items() if key != 'type'}
        response = self.client.post('/api/criteria/validate', json={'questions': {'role_python': question}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['questions']['role_python']['type'], 'choice')

    def test_invalid_payloads_return_field_errors(self) -> None:
        for body in ({}, {'questions': {}}, {'questions': 'invalid json'}, {'questions': '[]'},
                     {'questions': None}, {'questions': {'python': QUESTION}},
                     {'questions': {'role_python': QUESTION}, 'unexpected': True},
                     {'questions': {f'role_q{i}': QUESTION for i in range(21)}}):
            with self.subTest(fields=list(body)):
                response = self.client.post('/api/criteria/validate', json=body)
                self.assertEqual(response.status_code, 422)
                self.assertIn('loc', response.json()['detail'][0])

    def test_invalid_questions_are_rejected(self) -> None:
        for mutate in (
            lambda question: question.update(type='score'),
            lambda question: question.update(instructions=' '),
            lambda question: question['criteria'].pop('insufficient_evidence'),
            lambda question: question['criteria'].update(meets=''),
            lambda question: question.update(extra='unexpected'),
        ):
            question = json.loads(json.dumps(QUESTION))
            mutate(question)
            for questions in ({'role_python': question}, json.dumps({'role_python': question})):
                response = self.client.post('/api/criteria/validate', json={'questions': questions})
                self.assertEqual(response.status_code, 422)

    def test_openapi_describes_working_endpoint(self) -> None:
        schema = self.client.get('/openapi.json').json()
        operation = schema['paths']['/api/criteria/validate']['post']
        self.assertIn('200', operation['responses'])
        self.assertNotIn('501', operation['responses'])
        self.assertIn('application/json', operation['requestBody']['content'])
