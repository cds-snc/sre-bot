import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import Header from './Header';
import { ThemeProvider, createTheme } from '@mui/material/styles';

// Mock theme tokens
jest.mock('../theme', () => ({
  tokens: (mode) => ({
    grey: {
      100: mode === 'dark' ? '#fff' : '#000',
    },
    greenAccent: {
      400: '#00ff00',
    },
  }),
}));

const renderWithTheme = (ui, theme) => {
  return render(
    <ThemeProvider theme={theme}>
      {ui}
    </ThemeProvider>
  );
};

test('renders Header component with title and subtitle', () => {
  const theme = createTheme({ palette: { mode: 'dark' } });
  renderWithTheme(<Header title="Test Title" subtitle="Test Subtitle" />, theme);

  // Check if the title is rendered with correct text
  const titleElement = screen.getByText(/Test Title/i);
  expect(titleElement).toBeInTheDocument();
  expect(titleElement).toHaveStyle('color: #fff'); // Grey color in dark mode

  // Check if the subtitle is rendered with correct text
  const subtitleElement = screen.getByText(/Test Subtitle/i);
  expect(subtitleElement).toBeInTheDocument();
  expect(subtitleElement).toHaveStyle('color: #00ff00'); // GreenAccent color
});

test('renders Header component with light mode', () => {
  const theme = createTheme({ palette: { mode: 'light' } });
  renderWithTheme(<Header title="Light Mode Title" subtitle="Light Mode Subtitle" />, theme);

  // Check if the title is rendered with correct text and color in light mode
  const titleElement = screen.getByText(/Light Mode Title/i);
  expect(titleElement).toBeInTheDocument();
  expect(titleElement).toHaveStyle('color: #000'); // Grey color in light mode

  // Check if the subtitle is rendered with correct text
  const subtitleElement = screen.getByText(/Light Mode Subtitle/i);
  expect(subtitleElement).toBeInTheDocument();
  expect(subtitleElement).toHaveStyle('color: #00ff00'); // GreenAccent color
});
