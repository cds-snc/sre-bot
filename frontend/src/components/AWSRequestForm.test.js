import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import AWSRequestForm from './AWSRequestForm';
import fetchMock from 'jest-fetch-mock';

fetchMock.enableMocks();

beforeEach(() => {
  fetch.resetMocks();
});

test('renders AWSRequestForm and fetches accounts', async () => {
  fetch.mockResponseOnce(JSON.stringify(['123', '456']));

  render(<AWSRequestForm />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/accounts'));

  expect(screen.getByText('Fill out the fields below to request access to the desired AWS account.')).toBeInTheDocument();
  expect(screen.getByLabelText('AWS Account')).toBeInTheDocument();
  expect(screen.getByLabelText('Reason for access')).toBeInTheDocument();
  expect(screen.getByLabelText('Start date and time')).toBeInTheDocument();
  expect(screen.getByLabelText('End date and time')).toBeInTheDocument();
});

test('handles form submission successfully', async () => {
  fetch.mockResponses(
    [JSON.stringify(['123', '456']), { status: 200 }],
    [JSON.stringify({}), { status: 200 }]
  );

  render(<AWSRequestForm />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/accounts'));

  fireEvent.change(screen.getByLabelText('AWS Account'), { target: { value: '123' } });
  fireEvent.change(screen.getByLabelText('Reason for access'), { target: { value: 'Testing' } });
  fireEvent.click(screen.getByText('Send request'));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/request_access',
    expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('123')
    })
  ));

  expect(screen.getByText('Request sent successfully. The SRE team will review the request and grant access if approved.')).toBeInTheDocument();
});

test('handles form submission failure', async () => {
  fetch.mockResponses(
    [JSON.stringify(['123', '456']), { status: 200 }],
    [JSON.stringify({ detail: 'Request failed' }), { status: 400 }]
  );

  render(<AWSRequestForm />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/accounts'));

  fireEvent.change(screen.getByLabelText('AWS Account'), { target: { value: '123' } });
  fireEvent.change(screen.getByLabelText('Reason for access'), { target: { value: 'Testing' } });
  fireEvent.click(screen.getByText('Send request'));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/request_access',
    expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('123')
    })
  ));

  expect(screen.getByText('Request failed')).toBeInTheDocument();
});