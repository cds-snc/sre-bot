import React, { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import { Select, TextField, Button, Typography, Box } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
//import { DemoContainer } from '@mui/x-date-pickers/internals/demo';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import Alert from '@mui/material/Alert';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);

const AWSRequestForm = ({ onSend }) => {
  const [account, setAccount] = useState('');
  const [accounts, setAccounts] = useState([]);
  const [reason, setReason] = useState('');
  const [startDate, setStartDate] = useState(dayjs());
  const [endDate, setEndDate] = useState(dayjs());
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');


  useEffect(() => {
    // Fetch accounts from API
    const fetchAccounts = async () => {
      try {
        const response = await fetch('/accounts');
        const data = await response.json();
        setAccounts(data); // Assuming the API returns an array of account numbers
      } catch (error) {
        console.error('Failed to fetch accounts', error);
      }
    };

    fetchAccounts();
  }, []);

  const handleChangeAccount = (event) => {
    setAccount(event.target.value);
  };

  const handleChangeReason = (event) => {
    setReason(event.target.value);
  };

  const handleSend = async () => {
   const requestData = {
      account,
      reason,
      startDate: startDate.utc().toISOString(),
      endDate: endDate.utc().toISOString(),
    };
    console.log("Request Data")
    console.log(requestData);

    try {
      const response = await fetch('/request_access', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
      });
      if (!response.ok) {
        const errorData = await response.json();
        setErrorMessage(errorData.detail || 'Request failed');
        setSuccessMessage('');
      } else {
        const result = await response.json();
        setSuccessMessage('Request sent successfully. The SRE team will review the request and grant access if approved.');
        setErrorMessage('');
        if (onSend) {
          onSend(result);
        }
        // Reset all fields after successful request
        setAccount('');
        setReason('');
        setStartDate(dayjs());
        setEndDate(dayjs());
      }
    } catch (error) {
      setErrorMessage('Failed to send request');
      setSuccessMessage('');
    }
  };
  // display the fields. If the post request is successful, hide the form and display a success message
  return (
    <div>
      {errorMessage && <Alert severity="error">{errorMessage}</Alert>}
      {successMessage && <Alert severity="success">{successMessage}</Alert>} 
      {!successMessage && (
        <>
      <Typography variant="body1" gutterBottom>
        Fill out the fields below to request access to the desired AWS account. 
      </Typography>
      <br />
      <FormControl variant="standard" sx={{ m: 1, minWidth: 120 }}>
        <InputLabel id="aws-account-select-label">AWS Account</InputLabel>
        <Select
            labelId="demo-simple-select-standard-label"
            id="demo-simple-select-standard"
            value={account}
            onChange={handleChangeAccount}
            label="AWS Account"
        >
          {accounts.map((acc) => (
            <MenuItem key={acc} value={acc}>
              {acc}
            </MenuItem>
          ))}
        </Select>
        <TextField 
          id="standard-basic" 
          label="Reason for access" 
          variant="standard" 
          sx={{ mt: 2 }} 
          value={reason} 
          onChange={handleChangeReason} 
        />
        <br />
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          {/* <DemoContainer components={['DateTimePicker']}> */}
          <Box components={['DateTimePicker']}>
            <DateTimePicker 
              label="Start date and time" 
              value={startDate} 
              onChange={(newValue) => setStartDate(newValue)} 
            />
          {/* </DemoContainer> */}
          </Box>
        </LocalizationProvider>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          {/* <DemoContainer components={['DateTimePicker']}> */}
          <Box components={['DateTimePicker']}>
            <DateTimePicker 
              label="End date and time" 
              value={endDate} 
              onChange={(newValue) => setEndDate(newValue)} 
            />
          {/* </DemoContainer> */}
          </Box>
        </LocalizationProvider>
        <br />
        <Button color="success" variant="contained" endIcon={<SendIcon />} onClick={handleSend} sx={{ mt: 2 }}>
          Send request
        </Button>
      </FormControl> 
      </>
      )}
    </div>
  );
};

AWSRequestForm.propTypes = {
  accounts: PropTypes.arrayOf(PropTypes.number).isRequired,
  onSend: PropTypes.func,
};

AWSRequestForm.defaultProps = {
  onSend: null,
};

export default AWSRequestForm;