from django.shortcuts import render, redirect, get_object_or_404
import braintree
from django.conf import settings
from flights.models import FlightBooking
import logging
import json
from django.http import JsonResponse
# Import cart models from app1
from app1.models import CartItem, FlightCartItem

# Configure logger
logger = logging.getLogger(__name__)

# Configure Braintree with more explicit environment setting
try:
    gateway = braintree.BraintreeGateway(
        braintree.Configuration(
            # Make sure this is set to the right environment (Sandbox or Production)
            braintree.Environment.Sandbox,
            merchant_id=settings.BRAINTREE_MERCHANT_ID,
            public_key=settings.BRAINTREE_PUBLIC_KEY,
            private_key=settings.BRAINTREE_PRIVATE_KEY
        )
    )
    logger.info("Braintree gateway initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Braintree gateway: {e}")
    gateway = None

def payment_process(request):
    logger.info(f"Payment process view called. Method: {request.method}")
    
    # Get booking ID from session
    booking_id = request.session.get('booking_id')
    if not booking_id:
        logger.warning("No booking_id in session")
        return redirect('home')
    
    # Get booking object
    try:
        booking = get_object_or_404(FlightBooking, id=booking_id, user=request.user)
        logger.info(f"Found booking {booking_id} for user {request.user.username}")
    except Exception as e:
        logger.error(f"Error retrieving booking {booking_id}: {e}")
        request.session['payment_error'] = "Could not retrieve booking information"
        return redirect('payments:canceled')
    
    # Check if already paid
    if booking.payment_status == 'CONFIRMED':
        return redirect('payments:done')
    
    # Format amount properly
    try:
        amount = f"{float(booking.total_price):.2f}"
        logger.info(f"Payment amount: {amount}")
    except Exception as e:
        logger.error(f"Error formatting amount: {e}")
        amount = "0.00"  # Default amount to prevent errors
    
    if request.method == 'POST':
        nonce = request.POST.get('payment_method_nonce')
        
        if not nonce:
            logger.error("Payment method nonce not found in request")
            return redirect('payments:canceled')
        
        logger.info(f"Processing payment with nonce for booking {booking_id}")
        
        try:
            # Create transaction
            result = gateway.transaction.sale({
                'amount': amount,
                'payment_method_nonce': nonce,
                'options': {
                    'submit_for_settlement': True
                }
            })
            
            if result.is_success:
                logger.info(f"Payment SUCCESS for booking {booking.id}. Transaction ID: {result.transaction.id}. Updating booking status.")
                try:
                    # 1. Update booking
                    booking.payment_status = 'CONFIRMED'
                    booking.booking_reference = result.transaction.id
                    booking.save()
                    logger.info(f"Booking {booking.id} status updated to CONFIRMED and saved.")
                    
                    # 2. Clear session booking_id
                    logger.info(f"Attempting to delete booking_id {booking_id} from session.")
                    if 'booking_id' in request.session:
                        del request.session['booking_id']
                        request.session.save() 
                        logger.info(f"Deleted booking_id {booking_id} from session and saved session.")
                    else:
                        logger.warning(f"booking_id {booking_id} was already missing from session before deletion attempt.")
                    
                    # 3. Clear corresponding cart items
                    try:
                        logger.info(f"Attempting to clear cart items for user {request.user.id} associated with booking {booking.id}")
                        # Since one booking represents the whole cart checkout in the current logic:
                        hotel_items_deleted, _ = CartItem.objects.filter(user=request.user).delete()
                        flight_items_deleted, _ = FlightCartItem.objects.filter(user=request.user).delete()
                        logger.info(f"Cart items cleared: Hotels={hotel_items_deleted}, Flights={flight_items_deleted}")
                    except Exception as cart_e:
                        logger.error(f"Error clearing cart items for user {request.user.id} after successful payment for booking {booking.id}: {cart_e}", exc_info=True)
                        # Log the error but continue to success page, as payment was successful.
                        
                    # 4. Redirect to success page
                    logger.info(f"Redirecting user to payments:done for booking {booking.id}")
                    return redirect('payments:done')
                    
                except Exception as e:
                     # Handle errors during DB update or session/cart clearing
                     logger.error(f"Error during post-payment processing for booking {booking.id}: {e}", exc_info=True)
                     # Since payment succeeded, maybe redirect to 'done' but show a message?
                     # Or redirect to a specific error page?
                     # For now, redirecting to canceled might be safest to avoid confusion, but log thoroughly.
                     request.session['payment_error'] = "Payment confirmed, but error occurred during final processing. Please contact support."
                     return redirect('payments:canceled')
            else:
                error_msg = result.message if hasattr(result, 'message') else "Payment failed"
                logger.error(f"Payment failed: {error_msg}")
                request.session['payment_error'] = f"Payment failed: {error_msg}"
                return redirect('payments:canceled')
        
        except Exception as e:
            logger.exception(f"Exception during payment processing: {e}")
            request.session['payment_error'] = f"An unexpected error occurred: {str(e)[:100]}"
            return redirect('payments:canceled')
    
    else:  # GET request
        try:
            # Generate client token - most important part!
            if not gateway:
                logger.error("Braintree gateway not initialized")
                client_token = None
            else:
                client_token = gateway.client_token.generate()
                logger.info("Generated client token successfully")
        except Exception as e:
            logger.exception(f"Failed to generate client token: {e}")
            client_token = None
        
        context = {
            'client_token': client_token,
            'amount': amount,
            'booking': booking
        }
        
        return render(request, 'payments/payment.html', context)

def payment_done(request):
    # Try to get the user's most recent confirmed booking to display details
    if request.user.is_authenticated:
        try:
            from flights.models import FlightBooking
            from loginApp.models import UserActivity
            
            # Look for the most recent confirmed booking
            recent_booking = FlightBooking.objects.filter(
                user=request.user,
                payment_status='CONFIRMED'
            ).order_by('-booking_date').first()
            
            if recent_booking:
                # Log the successful booking as an activity
                if recent_booking.booking_details and recent_booking.booking_details.get('type') == 'Hotel':
                    hotel_name = recent_booking.booking_details.get('hotel_name', 'a hotel')
                    activity_title = f"Booked {hotel_name}"
                    activity_description = f"Completed booking at {hotel_name}"
                else:
                    activity_title = f"Booked flight: {recent_booking.origin} to {recent_booking.destination}"
                    activity_description = f"Completed flight booking from {recent_booking.origin} to {recent_booking.destination}"
                
                UserActivity.objects.create(
                    user=request.user,
                    activity_type='booking',
                    title=activity_title,
                    description=activity_description
                )
        except Exception as e:
            logger.error(f"Error logging booking activity: {e}")
    
    return render(request, 'payments/payment_done.html')

def payment_canceled(request):
    error = request.session.get('payment_error', 'Payment was canceled')
    if 'payment_error' in request.session:
        del request.session['payment_error']
    
    return render(request, 'payments/payment_canceled.html', {'error': error})
