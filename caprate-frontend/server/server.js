const express = require('express');
const axios = require('axios');
const cors = require('cors');
require('dotenv').config();

const app = express();
const port = 5001;

app.use(cors());
app.use(express.json());

const API_KEY = process.env.API_KEY;

app.get('/caprates', async (req, res) => {
  const { zpid } = req.query;

  if (!zpid) {
    return res.status(400).json({ error: 'ZPID is required' });
  }

  try {
    // Fetch property details
    const propertyResponse = await axios.get(`https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates`, {
      params: {
        access_token: API_KEY,
        zpid
      }
    });

    if (propertyResponse.data && propertyResponse.data.bundle && propertyResponse.data.bundle.length > 0) {
      const { Latitude, Longitude, address, zestimate, rentalZestimate } = propertyResponse.data.bundle[0];

      if (Latitude && Longitude) {
        // Fetch nearby properties
        const nearbyResponse = await axios.get(`https://api.bridgedataoutput.com/api/v2/zestimates_v2/zestimates`, {
          params: {
            access_token: API_KEY,
            near: `${Latitude},${Longitude}`,
            limit: 200
          }
        });

        const properties = nearbyResponse.data.bundle.map(result => {
          const { address, zestimate, rentalZestimate } = result;
          const capRate = (rentalZestimate * 12) / zestimate * 100;

          return {
            address: address || '',
            zestimate: zestimate || 0,
            rentalZestimate: rentalZestimate || 0,
            capRate: `${capRate.toFixed(2)}%`
          };
        });

        res.json(properties);
      } else {
        res.status(400).json({ error: 'Latitude and longitude not found for the given ZPID.' });
      }
    } else {
      res.status(404).json({ error: 'No property found for the given ZPID.' });
    }
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error fetching data. Please try again.' });
  }
});

app.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});
