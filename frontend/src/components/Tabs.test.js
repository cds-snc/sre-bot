import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import BasicTabs from './Tabs';
import HomeIcon from '@mui/icons-material/Home';
import InfoIcon from '@mui/icons-material/Info';
import ContactMailIcon from '@mui/icons-material/ContactMail';

describe('BasicTabs Component', () => {
  const tabs = [
    { label: 'Home', icon: <HomeIcon />, content: <div>Home Content</div> },
    { label: 'Info', icon: <InfoIcon />, content: <div>Info Content</div> },
    { label: 'Contact', icon: <ContactMailIcon />, content: <div>Contact Content</div> },
  ];

  test('renders BasicTabs component with all tabs', () => {
    render(<BasicTabs tabs={tabs} />);
    
    // Check if all tab labels are rendered
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Info')).toBeInTheDocument();
    expect(screen.getByText('Contact')).toBeInTheDocument();
  });

  test('displays correct content when tabs are clicked', () => {
    render(<BasicTabs tabs={tabs} />);
    
    // Initially, the first tab's content should be displayed
    expect(screen.getByText('Home Content')).toBeInTheDocument();
    expect(screen.queryByText('Info Content')).not.toBeInTheDocument();
    expect(screen.queryByText('Contact Content')).not.toBeInTheDocument();

    // Click on the Info tab
    fireEvent.click(screen.getByText('Info'));
    expect(screen.getByText('Info Content')).toBeInTheDocument();
    expect(screen.queryByText('Home Content')).not.toBeInTheDocument();
    expect(screen.queryByText('Contact Content')).not.toBeInTheDocument();

    // Click on the Contact tab
    fireEvent.click(screen.getByText('Contact'));
    expect(screen.getByText('Contact Content')).toBeInTheDocument();
    expect(screen.queryByText('Home Content')).not.toBeInTheDocument();
    expect(screen.queryByText('Info Content')).not.toBeInTheDocument();
  });
});