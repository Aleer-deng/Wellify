# Wellify

The React frontend now connects to the Django backend for account access, activity, goals, challenges, points, rewards, notifications and staff administration.

Start Django in `Back-End` on port 8000, then run `npm.cmd run dev` in this folder and open **http://127.0.0.1:5173/**. Sign in with your Django username or email and password. Both servers must stay running.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for connection setup, configuration, browser tests and feature limits.

## Front-End Requirements
The front end is responsible for the user interface and user interaction on the web and mobile applications.
1. Functional requirements
No.	Requirement	Description
1	User registration	Interface for creating a new account.
2	User login	Secure login and logout pages.
3	User dashboard	Display steps, goals, points and progress.
4	Activity tracking	Display daily steps and physical activity records.
5	Goal setting	Allow users to set daily and weekly goals.
6	Rewards page	Display earned points and available rewards.
7	Points wallet	Show points balance and transaction history.
8	Reward redemption	Allow users to select and redeem available rewards.
9	User profile	Allow users to view and update personal details.
10	Notifications	Display reminders, achievements and reward updates.
11	Subscription page	Display subscription plans and account status.
12	Admin dashboard	Provide interfaces for managing users, rewards and reports.

2. Non-functional requirements
- Responsive design: Support mobile phones, tablets and desktops.
- Usability: Simple, attractive and easy-to-navigate interface.
- Performance: Fast loading and smooth navigation.
- Compatibility: Support modern web browsers and intended mobile devices.
- Accessibility: Readable text, clear buttons and suitable colour contrast.
- Security: Secure forms and protected user sessions.
3. Front-end technologies
Technology	Purpose
HTML5	Page structure
CSS3	Styling and layout
JavaScript	Interactive functionality
React.js	Web application interface
React Native	Mobile application interface
Figma	UI/UX design and prototyping

4. Main front-end pages
1. Welcome / Landing Page
2. Registration Page
3. Login Page
4. User Dashboard
5. Activity Tracking Page
6. Goals and Challenges Page
7. Rewards Catalogue
8. Points Wallet
9. User Profile
10. Notifications Page
11. Subscription Page
12. Admin Dashboard
