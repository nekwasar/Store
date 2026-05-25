# Store
Online store built with FastAPI and MongoDB, containerized with Docker Compose.

## Using the Project

Open the application in your browser:

```
http://localhost:80/
```

Log in to the admin panel using the credentials created in step 5:

```
http://localhost:80/admin/
```
Using the admin panel you can perform CRUD operations:

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/7f448672-7924-49b4-98de-fd75fc4bb167)

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/771f970c-5911-423a-b3ee-c59106f88072)

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/d47f560d-ae0a-4519-bb4c-da8bff4a9859)

# Features

## Coupon System

Using the admin panel you can create and manage discount coupons. Discount information will be stored in the order data.

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/98a8086b-6e13-4f95-8ae8-a4c555848402)

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/c13317b8-7f6b-4a67-8b06-cbcc5857fe22)

## Email notifications

The application sends email notifications that indicate the creation of an order and payment notifications that contain an invoice in PDF format. This functionality is implemented using Сelery and RabbitMQ.

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/c92021e2-0d7a-4684-adf8-16a8d329b30a)

![invoice](https://github.com/sammyjankins/fastapi_shop/assets/26933434/705c615a-e9ba-4704-8091-514551e5fd96)

## Recommendations

The application has a recommendation system. This functionality is implemented using Redis.

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/07f2f9d9-994b-4eba-bfe1-f28c0c4e384c)

## Stripe

The application uses Stripe as a payment system.

![image](https://github.com/sammyjankins/fastapi_shop/assets/26933434/c40e2cec-ef24-41ea-9bc5-c8af5e08436c)


