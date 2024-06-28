import * as React from 'react';
import PropTypes from 'prop-types';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import { Select, TextField, Button, Typography } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import { DemoContainer } from '@mui/x-date-pickers/internals/demo';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';

const AWSRequestForm = ({ accounts, onSend }) => {
  const [account, setAccount] = React.useState('');

  const handleChange = (event) => {
    setAccount(event.target.value);
  };

  const handleSend = () => {
    if (onSend) {
      onSend(account);
    }
  };

  return (
    <div>
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
            onChange={handleChange}
            label="AWS Account"
        >
        <MenuItem value={12345}>12345</MenuItem>
        <MenuItem value={56789}>56789</MenuItem>
        </Select>
        <TextField id="standard-basic" label="Reason for access" variant="standard" sx={{ mt: 2 }} />
        <br />
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DemoContainer components={['DateTimePicker']}>
            <DateTimePicker label="Start date and time" />
          </DemoContainer>
        </LocalizationProvider>
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DemoContainer components={['DateTimePicker']}>
            <DateTimePicker label="End date and time" />
          </DemoContainer>
        </LocalizationProvider>
        <br />
        <Button color="success" variant="contained" endIcon={<SendIcon />} onClick={handleSend} sx={{ mt: 2 }}>
          Send request
        </Button>
      </FormControl>
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