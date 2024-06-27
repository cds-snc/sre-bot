import * as React from 'react';
import Paper from '@mui/material/Paper';
import { Typography, Box } from '@mui/material';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import PropTypes from 'prop-types';

// Column definitions for the table
const columns = [
    { id: 'account', label: 'Account', minWidth: 170 },
    { id: 'access_type', label: 'Type of Access', minWidth: 100 },
    {
      id: 'reason_for_access',
      label: 'Reason for Access',
      minWidth: 170,
    },
    {
      id: 'start_date',
      label: 'Start Date',
      minWidth: 170,
    },
    {
      id: 'end_date',
      label: 'End Date',
      minWidth: 170,
    },
    {
      id: 'status',
      label: 'Status',
      minWidth: 170,
    },
  ];
  
  // Function to transform API data to table row format
  const transformData = (data) => {
    return data.map(item => ({
      account: item.account_name.S,
      access_type: item.access_type.S,
      reason_for_access: item.rationale.S,
      start_date: new Date(parseFloat(item.start_date_time.N) * 1000).toLocaleString(),
      end_date: new Date(parseFloat(item.end_date_time.N) * 1000).toLocaleString(),
      status: item.expired.BOOL ? 'Expired' : 'Active'
    }));
  };

  const getTitleText = (endpoint_url) => {
    switch (endpoint_url) {
      case 'active_requests':
        return 'AWS Account access requests that are either pending (awaiting approval) or active (approved and not expired).';
      case 'past_requests':
        return 'AWS Account access requests that have expired.';
      default:
        return 'AWS Account Access requests';
    }
  };
  
  export default function AWSListRequests({endpoint_url}) {
    const [page, setPage] = React.useState(0);
    const [rowsPerPage, setRowsPerPage] = React.useState(10);
    const [rows, setRows] = React.useState([]);
  
    React.useEffect(() => {
      // Fetch data from the API
      const fetchData = async () => {
        try {
          //const response = await fetch('active_requests');
          const response = await fetch(endpoint_url);
          const data = await response.json();
          const transformedData = transformData(data);
          setRows(transformedData);
        } catch (error) {
          console.error('Error fetching data:', error);
        }
      };
  
      fetchData();
    }, [endpoint_url]);
  
    const handleChangePage = (event, newPage) => {
      setPage(newPage);
    };
  
    const handleChangeRowsPerPage = (event) => {
      setRowsPerPage(+event.target.value);
      setPage(0);
    };
  
    return (
      <Box>
        <Typography variant="h6" gutterBottom> 
          {getTitleText(endpoint_url)}
        </Typography>
        <br />
        <Paper sx={{ width: '100%', overflow: 'hidden' }}>
          <TableContainer sx={{ maxHeight: 440 }}>
            <Table stickyHeader aria-label="sticky table">
              <TableHead>
                <TableRow>
                  {columns.map((column) => (
                    <TableCell
                      key={column.id}
                      align={column.align}
                      style={{ minWidth: column.minWidth, fontWeight: 'bold'}}
                    >
                      {column.label}
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows
                  .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                  .map((row) => {
                    return (
                      <TableRow hover role="checkbox" tabIndex={-1} key={row.account}>
                        {columns.map((column) => {
                          const value = row[column.id];
                          return (
                            <TableCell key={column.id} align={column.align}>
                              {value}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    );
                  })}
              </TableBody>
            </Table>
          </TableContainer>
          <TablePagination
            rowsPerPageOptions={[10, 25, 100]}
            component="div"
            count={rows.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        </Paper>
      </Box>
    );
  }

  // Define PropTypes for the component
AWSListRequests.propTypes = {
    url: PropTypes.string.isRequired
  };