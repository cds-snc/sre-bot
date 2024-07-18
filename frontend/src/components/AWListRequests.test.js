import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import AWSListRequests from './AWSListRequests'; // Update this import

// Mock the fetch function
global.fetch = jest.fn();

beforeEach(() => {
  fetch.mockClear();
});

test('renders table for active requests', async () => {

  render(<AWSListRequests endpoint_url="active_requests" />);

  await waitFor(() => screen.getByText('AWS Account access requests that are either pending (awaiting approval) or active (approved and not expired).'));

   expect(screen.getByText('Type of Access')).toBeInTheDocument();
   expect(screen.getByText('Account')).toBeInTheDocument();
   expect(screen.getByText('Reason for Access')).toBeInTheDocument();
   expect(screen.getByText('Start Date')).toBeInTheDocument();
   expect(screen.getByText('End Date')).toBeInTheDocument();
   expect(screen.getByText('Status')).toBeInTheDocument();
});

test('renders table for past requests', async () => {

    render(<AWSListRequests endpoint_url="past_requests" />);
  
    await waitFor(() => screen.getByText('AWS Account access requests that have expired.'))
  
     expect(screen.getByText('Type of Access')).toBeInTheDocument();
     expect(screen.getByText('Account')).toBeInTheDocument();
     expect(screen.getByText('Reason for Access')).toBeInTheDocument();
     expect(screen.getByText('Start Date')).toBeInTheDocument();
     expect(screen.getByText('End Date')).toBeInTheDocument();
     expect(screen.getByText('Status')).toBeInTheDocument();
  });

test('handles fetch error gracefully active requests', async () => {
  fetch.mockRejectedValueOnce(new Error('Failed to fetch'));

  render(<AWSListRequests endpoint_url="active_requests" />);

  await waitFor(() => screen.getByText('AWS Account access requests that are either pending (awaiting approval) or active (approved and not expired).'));

  expect(screen.queryByText('ExampleAccount')).not.toBeInTheDocument();
  expect(screen.queryByText('ExampleAccount2')).not.toBeInTheDocument();
  expect(screen.queryByText('read')).not.toBeInTheDocument();
  expect(screen.queryByText('write')).not.toBeInTheDocument();
});

test('handles fetch error gracefully past requests', async () => {
    fetch.mockRejectedValueOnce(new Error('Failed to fetch'));
  
    render(<AWSListRequests endpoint_url="past_requests" />);
  
    await waitFor(() => screen.getByText('AWS Account access requests that have expired.'));
  
    expect(screen.queryByText('ExampleAccount')).not.toBeInTheDocument();
    expect(screen.queryByText('ExampleAccount2')).not.toBeInTheDocument();
    expect(screen.queryByText('read')).not.toBeInTheDocument();
    expect(screen.queryByText('write')).not.toBeInTheDocument();
  });