# Software Requirements Specification (SRS) - Finedine

## 1. Introduction
Finedine is a comprehensive restaurant ordering and reservation system designed to streamline operations and enhance user experience.

## 2. General Description
The system provides tailored interfaces for customers, administrators, and staff (waiters, kitchen, cashiers).

## 3. Functional Requirements

### 3.1 User Management
- **Auth**: Secure login/registration.
- **Profiles**: Comprehensive profile tracking. Users **MUST** complete their layout (Full Name, Phone, Address) before placing orders.
- **Security**: Password reset with 30-minute token expiry; Email verification flow.
- **Roles**: Support for `admin`, `waiter`, `kitchen`, `cashier`, and `customer`.

### 3.2 Order Management
- **Menu**: Categorized menu browsing with availability status.
- **Cart**: Add/Update/Remove items.
- **Checkout**: Support for Cash on Delivery and Online Payment (bKash).
- **History**: View past orders and download PDF invoices.
- **Types**: Support for `dine_in` and `takeaway`.

### 3.3 Inventory & Stock Control
- **Tracking**: Real-time stock decrement upon order placement.
- **Restocking**: Automatic increment if orders are cancelled.
- **Thresholds**: Low stock alerts when items fall below a defined threshold.
- **Management**: Admin interface for updating stock levels.

### 3.4 Table Reservations
- **Booking**: Users can reserve tables with specific date, time, duration, and guest count.
- **Confirmation**: Admin approval/confirmation flow.
- **Identifiers**: Each reservation has a unique 12-character ID.

### 3.5 Loyalty Program
- **Engagement**: Users earn **1 point for every $10 spent**.
- **Redemption**: Future support for point redemption for discounts.

### 3.6 Staff & Operations
- **Shifts**: Track staff schedules and attendance.
- **Interface**: Optimized views for Kitchen (order status) and Waiters (table assignment).

### 3.7 Analytics & Reporting
- **Sales**: Daily and periodic sales reports.
- **Popularity**: Tracking best-selling dishes based on order volume and ratings.

## 4. Non-Functional Requirements
- **Security**: CSRF protection on all forms.
- **Data Integrity**: Role-based access control (RBAC) enforced on all management routes.
- **Performance**: Efficient handling of concurrent orders and reservations.
