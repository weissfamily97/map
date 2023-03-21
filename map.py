import time
import pycurl
import io
import board
import neopixel
import smbus

# Used for printing to the console in different colors
class bcolors:
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    OKRED   = '\033[91m'
    OKVIOLET  = '\033[35m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'

# Enumerate the NeoPixel colors
GREEN = 0
BLUE = 1
MAGENTA = 2
RED = 3

# Lux Sensor Defines
LIGHT_SENSOR_I2C_ADDR = 0x10
COMMAND_REG = 0x00
LIGHT_VAL_REG = 0x05
POWER_ON = 0x00
POWER_OFF = 0x01
MAX_BRIGHT = 10

# Print colors 
PRINT_COLOR = [bcolors.OKGREEN, bcolors.OKBLUE, bcolors.OKVIOLET, bcolors.OKRED]

# Create a list of all the airports we want to get METARs for
AIRPORTS = ["KAVX.TXT", "KRNO.TXT", "KTTD.TXT", "CYQL.TXT", "KRXE.TXT", "KJAC.TXT",\
            "KPVU.TXT", "KGCN.TXT", "KLXV.TXT", "KSBS.TXT", "KCUT.TXT", "KGCK.TXT",\
            "KSSF.TXT", "KEDC.TXT", "KTKI.TXT", "KADM.TXT", "KPNC.TXT", "KHUT.TXT",\
            "KTOP.TXT", "KSTJ.TXT", "KLXT.TXT", "KFAM.TXT", "KCGI.TXT", "KSIK.TXT",\
            "KNEW.TXT", "KNPA.TXT", "KDTS.TXT", "KNQX.TXT", "MYGF.TXT", "KISM.TXT",\
            "KARW.TXT", "KGKT.TXT", "KLOU.TXT", "KHFY.TXT", "KCDI.TXT", "KTTA.TXT",\
            "KFFA.TXT", "KTGI.TXT", "KCGS.TXT", "KISP.TXT", "KBID.TXT", "KALB.TXT",\
            "KSJX.TXT", "KOSH.TXT", "KDLL.TXT", "KDYT.TXT"]

# Tuples to send to the NeoPixels [R,G,B]
#               GREEN     BLUE    PURPLE     RED
PIXEL_COLOR = [[0,1,0], [0,0,2], [1,0,2], [1,0,0]]

# Base URL
BASE_URL = 'https://tgftp.nws.noaa.gov/data/observations/metar/stations/'


#-------------------------------------------------------------------------------
#
# This function goes through the tokenized METAR and decodes the visibility.
# The format of the visibility varies much more than others, so requires 
# special handling
# Handle all the different formats. These could be:
#   1/2SM
#   1 3/8SM
#   M1/4SM
#   10SM
#   1SM
#   1 SM
#   P6SM
#
#-------------------------------------------------------------------------------
def get_visibility(tokens):
    
    visibility = GREEN
    
    for i, token in enumerate(tokens):
        
        # Found "SM", or "Statue Miles"...indicates this token is for visibility
        if token.find('SM') >= 0 and token.find('KISM') <= 0:
            # Check if the first character is 'P' or 'M'.  If so, eliminate it
            if token[0] == 'P':
                token = token.lstrip("P")
            if token[0] == 'M':
                token = token.lstrip("M")

            # See if there is a '/', meaning the visibility has a fraction in it
            if token.find('/') >= 0:
                # Convert the portion right of the decimal to float
                vis = float(token[0]) / float(token[2])
                
                # Check if there is a whole number portion (is it 1 1/2 or just 1/2)
                try:
                    vis += float(tokens[i-1])
                except ValueError:
                    pass

            # Check if of the form  '1 SM'
            elif len(token) <= 2:
                vis = 1.0

            # Get the position of the 'S'.  Everything preceding is a number
            elif token[2] == 'S':
                vis = float(token[0:2])         # 10SM
            else:
                vis = float(token[0:1])         # 4SM
            
            #print("Visibility: " + str(vis))
            
            # < 1mi is LIFR
            if vis <= 1.0:
                visibility = MAGENTA
            # < 3mi is IFR
            elif vis <= 3.0:
                visibility = RED
            # < 5mi is MVFR
            elif vis <= 5.0:
                visibility = BLUE
            # otherwise VFR
            else:                
                visibility = GREEN
    
            break
            
    return (visibility)
    

#-------------------------------------------------------------------------------
#
# This function takes an airport identifier as a string input and returns
# the hex color (as a tuple) based on its current weather
#
#-------------------------------------------------------------------------------
def get_airport_color(airport):
    # Create the complete url for this airport
    url = BASE_URL + airport

    # cURL the METAR
    buffer = io.BytesIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buffer)
    try:
        c.perform()
    except:
        print("curl failed")
        pass
    c.close()   
    body = buffer.getvalue().decode("utf-8")
    print(body)
    tokens = body.split(" ")

    # Declare vars
    speed = GREEN
    ceiling = GREEN
    visibility = GREEN  
    
    # Parse the METAR to determine VFR(green), MVFR(blue), IFR(magenta), LIFR(red)
    # Loop through the split string
    for token in tokens:
        # look for wind speed
        pos = token.find('KT')
        if pos >= 0:
            # This check is necessary to make sure this is a windspeed token, 
            # and not an airport code token, since some airport codes may also
            # contain 'KT', for example: 'KTGP' or 'KLKT'
            if token[pos - 1].isnumeric():
                #print("Wind Speed: " + token[3:5])
                if int(token[3:5]) < 15:
                    speed = GREEN
                # if wind speed is greater than 15kts, go blue
                elif int(token[3:5]) < 20:
                    speed = BLUE
                # if wind speed is greater than 20kts, go red
                elif int(token[3:5]) < 25:
                    speed = RED
                # if wind speed is greater than 25kts, go magenta
                else:
                    speed = MAGENTA
            
        
        # Look for "overcast" or "broken" to determine the ceiling
        # We don't care about "scattered" or "few", as those don't constitute
        # a ceiling
        # Note: there can be multiple BKN tokens...take the first one (lowest altitude)
        elif token.find('OVC') >= 0 or token.find('BKN') >= 0:
            if ceiling == GREEN:
                #print("Ceiling: " + token[3:6])
                # < 500ft is LIFR
                if int(token[3:6]) < 5:
                    ceiling = MAGENTA
                # < 1000ft is IFR
                elif int(token[3:6]) < 10:
                    ceiling = RED
                # < 3000ft is MVFR
                elif int(token[3:6]) < 30:
                    ceiling = BLUE
        
    # look for visibility
    visibility = get_visibility(tokens)
    
    # Display the most severe condition
    if speed == MAGENTA or ceiling == MAGENTA or visibility == MAGENTA:
        condition = MAGENTA
    elif speed == RED or ceiling == RED or visibility == RED:
        condition = RED
    elif speed == BLUE or ceiling == BLUE or visibility == BLUE:
        condition = BLUE
    else:
        condition = GREEN
            
    return (condition)

#-------------------------------------------------------------------------------
#
# calc_lux - Reads the light sensor and calculates the scale factor
#
#-------------------------------------------------------------------------------
def calc_lux():

    # Set up the I2C
    bus = smbus.SMBus(1)

    # Turn the sensor on
    bus.write_byte_data(LIGHT_SENSOR_I2C_ADDR, COMMAND_REG, POWER_ON)
    
    # Wait 400ms
    time.sleep(0.4)
    
    # Read visible light intensity 
    lux = bus.read_word_data(LIGHT_SENSOR_I2C_ADDR, LIGHT_VAL_REG)

    # Turn the sensor off
    bus.write_byte_data(LIGHT_SENSOR_I2C_ADDR, COMMAND_REG, POWER_OFF)
    
    print("Read LUX = ", lux)
        
    # Scale the lux to a value between 0 and MAX_BRIGHT
    if (lux < 2000):
        lux = 1
    elif (lux < 3000):
        lux = 2
    elif (lux < 4000):
        lux = 3
    elif (lux < 5000):
        lux = 5
    else:
        lux = 10
        
    print("Scaled LUX = ", lux)
    
    return (lux)
    
#-------------------------------------------------------------------------------
#
# Main Entry point for program
#
#-------------------------------------------------------------------------------
def main(): 
    # This board will use GPIO 18 for PWM, and have 46 Pixels
    pixels = neopixel.NeoPixel(board.D18, len(AIRPORTS), auto_write=False, pixel_order=neopixel.RGB)

    # Loop through all colors, and display
    for color in PIXEL_COLOR:
        for i in range(len(AIRPORTS)):
            pixels[i] = color
        pixels.show()
        time.sleep(1)




    # Loop continually
    while True:
        try:            
            # Read the LUX sensor
            lux = calc_lux()

            # Loop through all airports
            for i, airport in enumerate(AIRPORTS):
                # Get the color based on the current weather
                col = get_airport_color(airport)
                
                # Scale the brightness 
                scaled_col = tuple(lux*x for x in PIXEL_COLOR[col])
                
                # Write it out to the NeoPixel string
                pixels[i] = scaled_col
                
                # Print the color
                print(PRINT_COLOR[col] + airport[0:4] + bcolors.ENDC)
                
        except ValueError:
            pass

        pixels.show()

        # Sleep for 1 second
        print("Wait for 1s...")
        time.sleep(1)
            
#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
