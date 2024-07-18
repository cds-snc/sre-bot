import Header from "../../components/Header";
import BasicTabs from "../../components/Tabs";
import AWSRequestForm from "../../components/AWSRequestForm";
import AWSListRequests from "../../components/AWSListRequests"; 
import { Box } from "@mui/material";
import * as React from 'react';
import FiberNewIcon from '@mui/icons-material/FiberNew';
import LibraryBooksIcon from '@mui/icons-material/LibraryBooks';
import ManageHistoryIcon from '@mui/icons-material/ManageHistory';

const AWS_Access= () => {
  const tabs = [
    { label: 'New Request', content: <AWSRequestForm />, icon: <FiberNewIcon />},
    { label: 'Upcoming Requests', content: <AWSListRequests endpoint_url="active_requests"/>, icon: <LibraryBooksIcon />},
    { label: 'Past Requests', content: <AWSListRequests endpoint_url="past_requests" /> , icon: <ManageHistoryIcon />},
  ];
    return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="AWS Access" />
      </Box>
      <div>
        <BasicTabs tabs={tabs} />
      </div>
      </Box>
    );
  }

export default AWS_Access;