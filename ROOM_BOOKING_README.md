# LBS Room Booking Automation

This script automates the process of booking study rooms on lbsmobile.london.edu.

## Files

- **book_room.py** - Main room booking script
- **room_booking_config.json** - Configuration file for booking parameters

## Configuration

Edit `room_booking_config.json` to set your booking parameters:

```json
{
  "booking_date": "2025-11-25",      // Format: YYYY-MM-DD
  "start_time": "14:00",             // Format: HH:MM (24-hour)
  "duration_hours": 3,               // Duration in hours (0.5 to 3)
  "attendees": 5,                    // Number of attendees (1-10)
  "study_group_name": "AI Cup group 19",
  "project_name": "Final Project",
  "building": "Sussex Place"         // Options: "North Building", "Sammy Ofer Centre", "Sussex Place"
}
```

## Usage

1. **Configure your booking** by editing `room_booking_config.json`

2. **Run the script:**
   ```bash
   python3 book_room.py
   ```

3. **Login:**
   - The browser will open to lbsmobile.london.edu
   - The "Sign In" button will be clicked automatically
   - Complete Microsoft MFA authentication manually

4. **Automatic process:**
   - Navigates to "My Bookings"
   - Clicks "Book Room"
   - Fills in all booking details from config
   - Selects the first available room
   - Completes the booking

## Notes

- **Login Required:** Each run requires manual Microsoft MFA authentication.

- **Building Codes:**
  - "North Building" → NB
  - "Sammy Ofer Centre" → SOC
  - "Sussex Place" → Susx Plc

- **Duration Options:** The script supports durations from 0.5 to 3 hours in 30-minute increments.

- **Room Selection:** The script automatically selects the first available room matching your criteria.

- **Loading Time:** The "Available Rooms" page takes a few seconds to load. The script includes appropriate wait times.

## Troubleshooting

**No rooms available:**
- Try different times or dates
- Check if the building selection is correct

**Form fields not filling:**
- Ensure the date format in config is YYYY-MM-DD
- Ensure the time format is HH:MM (24-hour)
- Check that duration_hours is between 0.5 and 3

## Example Workflow

```bash
# 1. Edit configuration
nano room_booking_config.json

# 2. Run the booking script
python3 book_room.py

# 3. Complete Microsoft MFA when prompted

# 4. Script automatically books the room

# 5. Browser stays open for verification
```

## Success Indicators

When booking is successful, you'll see:
```
================================================================================
✓ BOOKING SUCCESSFUL!
================================================================================
Room booked: NB.1.03 Executive Group Room
Date: 2025-11-25
Time: 14:00
Duration: 3 hours
Title: AI Cup group 19 - Final Project
```

## Integration with Study Group Manager

This room booking script runs independently from `run.py` (the study group assignment manager). They serve different purposes:

- **run.py** - Extracts assignments and study group member information from learning.london.edu
- **book_room.py** - Books study rooms on lbsmobile.london.edu

Both scripts use similar patterns for login but operate on different websites.
