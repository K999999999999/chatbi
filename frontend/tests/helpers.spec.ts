import { test, expect } from '@playwright/test';
import { isFinalExecutionResponse } from './helpers';

function executionResponse(status: string, method = 'GET', path = '/api/v1/executions/00000000-0000-4000-8000-000000000000') {
  return {
    url: () => `http://127.0.0.1:8080${path}`,
    request: () => ({ method: () => method }),
    json: async () => ({ execution: { status } }),
  };
}

test('execution response predicate waits past polling states and recognizes terminal states', async () => {
  expect(await isFinalExecutionResponse(executionResponse('running'))).toBe(false);
  expect(await isFinalExecutionResponse(executionResponse('succeeded'))).toBe(true);
  expect(await isFinalExecutionResponse(executionResponse('failed'))).toBe(true);
  expect(await isFinalExecutionResponse(executionResponse(
    'succeeded', 'GET', '/api/v1/executions/00000000-0000-4000-8000-000000000000/events',
  ))).toBe(false);
  expect(await isFinalExecutionResponse(executionResponse('succeeded', 'POST'))).toBe(false);
});
