-- Q1. Retrieve all successful bookings
SELECT *
FROM ola_rides
WHERE Booking_Status = 'Success';

-- Q2. Average ride distance for each vehicle type
-- (successful rides only: cancelled rides have distance 0)
SELECT Vehicle_Type,
       ROUND(AVG(Ride_Distance), 2) AS avg_distance_km
FROM ola_rides
WHERE Booking_Status = 'Success'
GROUP BY Vehicle_Type
ORDER BY avg_distance_km DESC;

-- Q3. Total number of rides cancelled by customers
SELECT COUNT(*) AS cancelled_by_customer
FROM ola_rides
WHERE Booking_Status = 'Canceled by Customer';

-- Q4. Top 5 customers who booked the highest number of rides
SELECT Customer_ID,
       COUNT(*) AS total_rides
FROM ola_rides
GROUP BY Customer_ID
ORDER BY total_rides DESC, Customer_ID
LIMIT 5;

-- Q5. Rides cancelled by drivers due to personal and car-related issues
SELECT COUNT(*) AS driver_cancel_personal_car
FROM ola_rides
WHERE Canceled_Rides_by_Driver = 'Personal & Car related issue';

-- Q6. Maximum and minimum driver ratings for Prime Sedan bookings
SELECT MAX(Driver_Ratings) AS max_driver_rating,
       MIN(Driver_Ratings) AS min_driver_rating
FROM ola_rides
WHERE Vehicle_Type = 'Prime Sedan';

-- Q7. All rides where payment was made using UPI
SELECT *
FROM ola_rides
WHERE Payment_Method = 'UPI';

-- Q8. Average customer rating per vehicle type
SELECT Vehicle_Type,
       ROUND(AVG(Customer_Rating), 2) AS avg_customer_rating
FROM ola_rides
GROUP BY Vehicle_Type
ORDER BY avg_customer_rating DESC;

-- Q9. Total booking value of rides completed successfully
SELECT SUM(Booking_Value) AS total_booking_value
FROM ola_rides
WHERE Booking_Status = 'Success';

-- Q10. All incomplete rides along with the reason
SELECT Booking_ID, Date, Vehicle_Type, Pickup_Location, Drop_Location,
       Incomplete_Rides_Reason
FROM ola_rides
WHERE Incomplete_Rides = 'Yes';