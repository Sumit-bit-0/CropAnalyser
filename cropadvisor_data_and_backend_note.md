# CropAdvisor — Data, Backend, and Claude Setup Note

## Purpose
Build CropAdvisor as a practical crop recommendation system that combines:
- soil suitability
- regional crop history
- market profitability
- weather intelligence
- optional remote sensing later

The goal is to make the app usable with minimal manual input and enough backend intelligence to produce trustworthy recommendations.

---

## 1) What data sources the project needs

### A. Soil / crop recommendation data
Use this for the core agronomic model.

Expected columns:
- N
- P
- K
- temperature
- humidity
- pH
- rainfall
- crop label

Use:
- train the baseline crop suitability model
- keep as the current "Simple Mode"

---

### B. Crop production / regional history data
Use this for proving which crops actually work in a district or region.

Expected columns:
- state
- district
- season
- crop
- area
- production
- yield

Use:
- regional crop fit score
- historical crop success lookup
- district-wise ranking support

---

### C. Market / mandi price data
Use this to estimate profitability.

Expected columns:
- date
- state
- district
- market
- crop
- min_price
- max_price
- modal_price

Use:
- profit scoring
- price trend analysis
- crop ranking by market value

---

### D. Weather data
Use this to reduce manual input and improve predictions.

Expected values:
- temperature
- rainfall
- humidity
- forecast risk signals
- historical climate patterns

Use:
- automatic weather fill
- season risk adjustment
- location-based advisory

Recommended first choice:
- Open-Meteo for live + forecast weather

Secondary option:
- NASA POWER for historical climate analysis

---

### E. Remote sensing / NDVI data
Use this later, not in the first MVP.

Expected values:
- NDVI
- vegetation health
- moisture proxy
- field stress indicators

Use:
- field condition scoring
- future precision advisory

Possible sources:
- Google Earth Engine
- Sentinel-based services

---

## 2) Recommended build order

### Phase 1 — MVP
Build only the pieces needed to ship a useful product:
- soil recommendation model
- regional crop history lookup
- market price ranking
- explanation layer
- basic backend integration

Keep the existing 7-input model as:
- Simple Mode

Add a new user-friendly flow as:
- Smart Mode

Smart Mode should allow:
- location
- season
- irrigation yes/no
- farming goal
- optional soil values


### Phase 2 — Weather automation
Add automatic weather fetch using Open-Meteo.

This removes the need for users to enter:
- rainfall
- temperature
- humidity

Use GPS or location input to fetch weather automatically.


### Phase 3 — Historical climate intelligence
Add NASA POWER for climate history and agricultural analysis.

Use this for:
- seasonal trend checks
- historical rainfall patterns
- drought risk comparison
- long-range climate signals


### Phase 4 — Satellite intelligence
Add NDVI and field health data later.

Use this for:
- crop stress detection
- vegetation health scoring
- future precision farming features

---

## 3) Backend structure

### Suggested backend services

#### A. Crop suitability service
Responsible for:
- predicting crop match from soil/weather inputs
- returning ranked suitability scores

#### B. Regional intelligence service
Responsible for:
- reading district/state crop history
- scoring crops based on local success

#### C. Market intelligence service
Responsible for:
- reading price data
- computing profit potential
- ranking crops by financial return

#### D. Weather service
Responsible for:
- calling Open-Meteo
- normalizing forecast and historical weather
- converting coordinates into usable farm context

#### E. Fusion / ranking service
Responsible for:
- combining all scores
- producing final top crop recommendations
- generating explanation text

---

## 4) Recommended database tables

### `soil_recommendation`
Stores the soil model dataset.

### `district_crop_history`
Stores historical crop performance by district and season.

### `market_prices`
Stores mandi and price trend data.

### `weather_cache`
Stores weather responses pulled from Open-Meteo.

### `field_profiles`
Stores user-specific field data:
- location
- soil values
- irrigation
- crop history
- goal

### `recommendation_runs`
Stores every recommendation returned to the user:
- inputs used
- scores
- final crops
- explanation
- timestamp

This makes the app debuggable and improvable.

---

## 5) Open-Meteo backend integration plan

### Why Open-Meteo first
Use it because it is the simplest way to add live weather without a complicated setup.

Use it to fetch:
- temperature
- rainfall
- humidity
- forecast values
- past weather if needed

### Backend flow
1. User enters location or GPS coordinates.
2. Backend converts location into latitude and longitude.
3. Backend calls Open-Meteo.
4. Backend stores the response in `weather_cache`.
5. Recommendation engine uses weather data in scoring.
6. App returns top crops with explanation.

### Best practice
- cache API responses
- avoid repeated calls for the same location and day
- keep weather calls isolated in one service

---

## 6) Tools required for Claude-assisted development

Claude should help with planning, code generation, and cleanup. To use Claude effectively, keep these tools and assets ready:

### A. Project documentation
- this note
- feature list
- user flow
- database schema
- API contract
- scoring logic explanation

### B. Dataset samples
- small CSV samples from each source
- column names documented clearly
- crop name mapping sheet

### C. Backend stack
Recommended:
- Python
- FastAPI
- Pandas
- Scikit-learn
- XGBoost or LightGBM
- PostgreSQL

### D. Utility tools
- requests for API calls
- pydantic for request validation
- sqlalchemy or an equivalent DB layer
- python-dotenv for environment variables
- logging for debugging
- cache layer such as Redis if needed

### E. Claude tasks
Use Claude for:
- turning the idea into a build plan
- writing backend service code
- writing model logic
- designing explanation text
- mapping inconsistent crop names
- cleaning dataset schemas
- generating API endpoints

---

## 7) What to store in environment variables

Keep secrets and configuration out of code.

Store:
- weather API base URLs if needed
- database connection string
- satellite service credentials
- any paid API keys
- deployment secrets

Suggested `.env` entries:
- `DATABASE_URL`
- `OPEN_METEO_BASE_URL`
- `NASA_POWER_BASE_URL`
- `GEOCODING_API_KEY` if a paid geocoder is used
- `SATELLITE_API_KEY` if added later

---

## 8) Practical recommendation

For the current stage:
- use Open-Meteo for weather
- download crop production data
- download mandi price data
- keep NASA POWER for later climate analysis
- add NDVI only after the MVP is working

This keeps the project practical, faster to build, and easier for users.

---

## 9) MVP deliverable checklist

Before launch, the project should be able to:
- accept location and crop goal
- auto-fetch weather
- read district crop history
- read market prices
- rank crops
- explain why each crop is recommended
- save results for later review

---

## 10) Next implementation step

Build the backend in this order:
1. database schema
2. weather integration
3. crop history loader
4. market price loader
5. scoring layer
6. explanation layer
7. frontend connection

That is the cleanest path from idea to working product.

