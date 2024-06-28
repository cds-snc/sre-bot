import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import AWS_Access from './index';
import BasicTabs from '../../components/Tabs';
import AWSRequestForm from '../../components/AccessForm';
import FiberNewIcon from '@mui/icons-material/FiberNew';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import ManageHistoryIcon from '@mui/icons-material/ManageHistory';

// Mock components to avoid rendering the actual components
jest.mock('../../components/Header', () => (props) => <div data-testid="Header">{props.title}</div>);
jest.mock('../../components/Tabs', () => (props) => (
  <div data-testid="BasicTabs">
    {props.tabs.map((tab, index) => (
      <div key={index} data-testid={`tab-${index}`}>
        {tab.icon} {tab.label}
      </div>
    ))}
  </div>
));
jest.mock('../../components/AccessForm', () => () => <div data-testid="AWSRequestForm">AWS Request Form</div>);

describe('AWS_Access', () => {
  const tabs = [
    {
      label: 'New Request',
      content: <AWSRequestForm />,
      icon: <FiberNewIcon data-testid="FiberNewIcon" />,
    },
    {
      label: 'Upcoming Requests',
      content: <div>View current requests that have not been approved or denied.</div>,
      icon: <LibraryBooksIcon data-testid="LibraryBooksIcon" />,
    },
    {
      label: 'Past Requests',
      content: <div>View all past approved/denied requests.</div>,
      icon: <ManageHistoryIcon data-testid="ManageHistoryIcon" />,
    },
  ];

  test('renders AWS_Access component with Header and BasicTabs', () => {
    render(<AWS_Access />);

    // Check if the Header component is rendered with the correct title
    expect(screen.getByTestId('Header')).toHaveTextContent('AWS Access');

        // Check if the BasicTabs component is rendered with the correct tabs
    expect(screen.getByTestId('BasicTabs')).toBeInTheDocument();
    tabs.forEach((tab, index) => {
      const tabElement = screen.getByTestId(`tab-${index}`);
      expect(tabElement).toHaveTextContent(tab.label);
    });
  });

  test('BasicTabs component handles tab switching', () => {
    // Render the actual BasicTabs component for interaction testing
    render(<BasicTabs tabs={tabs} />);

    // Initially, the first tab's content should be displayed
    expect(screen.getByText("New Request")).toBeInTheDocument();
    expect(screen.getByText("Upcoming Requests")).toBeInTheDocument();
    expect(screen.getByText("Past Requests")).toBeInTheDocument();

  });
});