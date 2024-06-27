import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import AWSRequestForm from './AWSRequestForm';

beforeEach(() => {
  jest.clearAllMocks();
});

test('renders AWSRequestForm and fetches accounts', async () => {
  global.fetch = jest.fn().mockResolvedValueOnce({
    json: async () => ['123', '456'],
  });

  render(<AWSRequestForm />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/accounts'));

  expect(screen.getByText('Fill out the fields below to request access to the desired AWS account.')).toBeInTheDocument();
  expect(screen.getByLabelText('AWS Account')).toBeInTheDocument();
  expect(screen.getByLabelText('Reason for access')).toBeInTheDocument();
  expect(screen.getByLabelText('Start date and time')).toBeInTheDocument();
  expect(screen.getByLabelText('End date and time')).toBeInTheDocument();
});

test('handles form submission', async () => {
  global.fetch = jest.fn()
    .mockResolvedValueOnce({
      json: async () => ['123', '456'],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

  render(<AWSRequestForm />);

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/accounts'));

  // Open the select dropdown
  fireEvent.mouseDown(screen.getByLabelText('AWS Account'));
  fireEvent.change(screen.getByLabelText('Reason for access'), { target: { value: 'Testing' } });
  fireEvent.click(screen.getByText('Send request'));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    '/request_access',
    expect.objectContaining({
      method: 'POST',
      body: expect.stringContaining('Testing')
    })
  ));

});