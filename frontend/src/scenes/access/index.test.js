import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import AWS_Access from './index';
import Header from '../../components/Header'; // Adjust the import based on the actual path
import { Box, Accordion, AccordionSummary, AccordionDetails, Typography } from '@mui/material';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import FiberNewIcon from '@mui/icons-material/FiberNew';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import ManageHistoryIcon from '@mui/icons-material/ManageHistory';

test('renders AWS_Access component with header', () => {
  render(<AWS_Access />);
  
  // Check if the Header component is rendered with the correct title
  expect(screen.getByText('AWS Access')).toBeInTheDocument();
});

test('renders all accordions with correct titles', () => {
  render(<AWS_Access />);
  
  // Check if all accordion headers are rendered with correct titles
  expect(screen.getByText('Request AWS Production Access')).toBeInTheDocument();
  expect(screen.getByText('View Outstanding Requests')).toBeInTheDocument();
  expect(screen.getByText('View Past Requests')).toBeInTheDocument();
});

test('renders accordion details with correct content', () => {
  render(<AWS_Access />);
  
  // Check if the accordion details are rendered with the correct content
  expect(screen.getByText('Request Access to an AWS account. The SRE team will be notified and the request will then be approved or denied.')).toBeInTheDocument();
  expect(screen.getByText('View current requests that have not been approved or denied.')).toBeInTheDocument();
  expect(screen.getByText('View all past approved/denied requests.')).toBeInTheDocument();
});