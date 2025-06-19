import React from 'react';
import { Container, Box, Typography } from '@mui/material';

const About = () => {
  return (
    <Container maxWidth="sm">
      <Box my={4}>
        <Typography variant="h4" component="h1" gutterBottom>
          About
        </Typography>
        <Typography variant="body1">
          This application uses a machine learning model to classify social media posts 
          for fake news detection. It was developed as part of a bachelor thesis project.
        </Typography>
      </Box>
    </Container>
  );
};

export default About;