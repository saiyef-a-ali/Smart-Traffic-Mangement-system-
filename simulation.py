import random
import time
import threading
import pygame
import sys
import os
import datetime

# Default values of signal timers
defaultGreen = {0:10, 1:10, 2:10, 3:10}
defaultRed = 150
defaultYellow = 2  # Changed from 5 to 2 seconds

signals = []
noOfSignals = 4
currentGreen = 0   # Indicates which signal is green currently
nextGreen = (currentGreen+1)%noOfSignals    # Indicates which signal will turn green next
currentYellow = 0   # Indicates whether yellow signal is on or off 

speeds = {'car':2.25, 'bus':1.8, 'truck':1.8, 'bike':2.5}  # average speeds of vehicles

# Coordinates of vehicles' start
x = {'right':[0,0,0], 'down':[755,727,697], 'left':[1400,1400,1400], 'up':[602,627,657]}    
y = {'right':[348,370,398], 'down':[0,0,0], 'left':[498,466,436], 'up':[800,800,800]}

vehicles = {'right': {0:[], 1:[], 2:[], 'crossed':0}, 'down': {0:[], 1:[], 2:[], 'crossed':0}, 'left': {0:[], 1:[], 2:[], 'crossed':0}, 'up': {0:[], 1:[], 2:[], 'crossed':0}}
vehicleTypes = {0:'car', 1:'bus', 2:'truck', 3:'bike'}
directionNumbers = {0:'right', 1:'down', 2:'left', 3:'up'}

# Coordinates of signal image, timer, and vehicle count
signalCoods = [(530,230),(810,230),(810,570),(530,570)]
signalTimerCoods = [(530,210),(810,210),(810,550),(530,550)]

# Coordinates of stop lines
stopLines = {'right': 590, 'down': 330, 'left': 800, 'up': 535}
defaultStop = {'right': 580, 'down': 320, 'left': 810, 'up': 545}

# Gap between vehicles
stoppingGap = 25    # stopping gap
movingGap = 25   # moving gap

# set allowed vehicle types here
allowedVehicleTypes = {'car': True, 'bus': True, 'truck': True, 'bike': True}
allowedVehicleTypesList = []
vehiclesTurned = {'right': {1:[], 2:[]}, 'down': {1:[], 2:[]}, 'left': {1:[], 2:[]}, 'up': {1:[], 2:[]}}
vehiclesNotTurned = {'right': {1:[], 2:[]}, 'down': {1:[], 2:[]}, 'left': {1:[], 2:[]}, 'up': {1:[], 2:[]}}
rotationAngle = 3
mid = {'right': {'x':705, 'y':445}, 'down': {'x':695, 'y':450}, 'left': {'x':695, 'y':425}, 'up': {'x':695, 'y':400}}
# set random or default green signal time here 
randomGreenSignalTimer = True
# set random green signal time range here 
randomGreenSignalTimerRange = [10,20]

timeElapsed = 0
simulationTime = 300
timeElapsedCoods = (1100,50)
vehicleCountTexts = ["0", "0", "0", "0"]
vehicleCountCoods = [(440,190),(920,190),(920,590),(440,590)]
waitingVehicleCountCoods = [(440,210),(920,210),(920,610),(440,610)]
waitingTimeCoods = [(440,230),(920,230),(920,630),(440,630)]

# Add these constants for the dynamic traffic management
LOW_WAIT_THRESHOLD = 10  # When wait time is below this, consider starting countdown
WAIT_TIME_THRESHOLD = 100  # Threshold for transitioning to yellow based on wait time
COUNTDOWN_TIME = 3  # Countdown time in seconds
WEIGHT_THRESHOLDS = [5, 10, 20, 30, 50]  # Thresholds for weighted waiting time
WEIGHT_VALUES = [1, 2, 3, 5, 8, 13]  # Weight values for each threshold range

# Variables for countdown management
countdown_active = False
countdown_timer = 0

# Add path for statistics report file
STATS_FOLDER = "stats"
if not os.path.exists(STATS_FOLDER):
    os.makedirs(STATS_FOLDER)

# Create a class to track and report simulation statistics
class SimulationStats:
    def __init__(self):
        self.start_time = datetime.datetime.now()
        # self.total_waiting_time = 0  # <-- Commented: not used for avg wait time
        self.vehicle_wait_times = []
        self.total_vehicles_completed = 0
        self.vehicles_on_road_over_time = []
        self.baseline_avg_wait = 35  # seconds per vehicle with fixed timing
        self.direction_stats = {
            'right': {'completed': 0, 'avg_wait': 0, 'total_wait': 0, 'crowds': []},
            'down': {'completed': 0, 'avg_wait': 0, 'total_wait': 0, 'crowds': []},
            'left': {'completed': 0, 'avg_wait': 0, 'total_wait': 0, 'crowds': []},
            'up': {'completed': 0, 'avg_wait': 0, 'total_wait': 0, 'crowds': []}
        }
        self.max_crowd = 0
        self.max_crowd_direction = None
        self.max_crowd_time = None

    def update(self, vehicles_dict):
        """Update statistics every second"""
        current_vehicles = 0
        for direction in vehicles_dict:
            if direction != 'crossed':
                for lane in [0, 1, 2]:
                    current_vehicles += len(vehicles_dict[direction][lane])
        self.vehicles_on_road_over_time.append(current_vehicles)

    def record_vehicle_completion(self, vehicle, direction):
        self.total_vehicles_completed += 1
        # Only add the actual (absolute) waiting time, not weighted
        self.vehicle_wait_times.append(vehicle.waiting_time)
        # self.total_waiting_time += vehicle.waiting_time  # <-- Commented: not used for avg wait time
        self.direction_stats[direction]['completed'] += 1
        self.direction_stats[direction]['total_wait'] += vehicle.waiting_time
        if self.direction_stats[direction]['completed'] > 0:
            self.direction_stats[direction]['avg_wait'] = (
                self.direction_stats[direction]['total_wait'] /
                self.direction_stats[direction]['completed']
            )

    def record_crowd_on_signal_change(self, vehicles_dict, timeElapsed):
        """Call this at every signal change to record max crowd at any road"""
        max_crowd_this_change = 0
        max_dir = None
        for direction in ['right', 'down', 'left', 'up']:
            crowd = sum(1 for lane in [0, 1, 2] for v in vehicles_dict[direction][lane] if v.crossed == 0)
            self.direction_stats[direction]['crowds'].append(crowd)
            if crowd > max_crowd_this_change:
                max_crowd_this_change = crowd
                max_dir = direction
        if max_crowd_this_change > self.max_crowd:
            self.max_crowd = max_crowd_this_change
            self.max_crowd_direction = max_dir
            self.max_crowd_time = timeElapsed

    def get_avg_waiting_time(self):
        # Average of all actual waiting times (in seconds) for all vehicles
        if not self.vehicle_wait_times:
            return 0
        return sum(self.vehicle_wait_times) / len(self.vehicle_wait_times)

    def get_avg_vehicles_on_road(self):
        if not self.vehicles_on_road_over_time:
            return 0
        return sum(self.vehicles_on_road_over_time) / len(self.vehicles_on_road_over_time)

    def estimate_fuel_reduction(self):
        current_avg_wait = self.get_avg_waiting_time()
        if current_avg_wait < self.baseline_avg_wait:
            reduction = (self.baseline_avg_wait - current_avg_wait) / self.baseline_avg_wait * 100
            return reduction
        return 0

    def save_to_file(self):
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(STATS_FOLDER, f"traffic_stats_{timestamp}.txt")
        with open(filename, 'w') as f:
            f.write("=== Traffic Simulation Statistics ===\n\n")
            f.write(f"Simulation started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Simulation duration: {timeElapsed} seconds\n")
            f.write(f"Total vehicles processed: {self.total_vehicles_completed}\n\n")
            f.write("=== Waiting Time Statistics ===\n")
            # f.write(f"Total waiting time: {self.total_waiting_time} seconds\n")  # <-- Commented: not used for avg wait time
            f.write(f"Average waiting time per vehicle: {self.get_avg_waiting_time():.2f} seconds\n\n")
            f.write("=== Traffic Volume Statistics ===\n")
            f.write(f"Average vehicles on road: {self.get_avg_vehicles_on_road():.2f}\n\n")
            f.write("=== Max Crowd Statistics ===\n")
            f.write(f"Maximum crowd at any road: {self.max_crowd}\n")
            if self.max_crowd_direction is not None:
                f.write(f"Occurred at direction: {self.max_crowd_direction} at simulation time: {self.max_crowd_time} sec\n")
            f.write("\n")
            f.write("=== Environmental Impact ===\n")
            f.write(f"Estimated fuel reduction: {self.estimate_fuel_reduction():.2f}%\n\n")
            f.write("=== Directional Statistics ===\n")
            for direction, stats in self.direction_stats.items():
                if stats['crowds']:
                    min_crowd = min(stats['crowds'])
                    max_crowd = max(stats['crowds'])
                    avg_crowd = sum(stats['crowds']) / len(stats['crowds'])
                else:
                    min_crowd = max_crowd = avg_crowd = 0
                f.write(f"{direction.capitalize()} direction:\n")
                f.write(f"  Completed vehicles: {stats['completed']}\n")
                f.write(f"  Average waiting time: {stats['avg_wait']:.2f} seconds\n")
                f.write(f"  Total waiting time: {stats['total_wait']} seconds\n")
                f.write(f"  Min/Avg/Max crowd at signal: {min_crowd}/{avg_crowd:.2f}/{max_crowd}\n\n")
        return filename

# Initialize global stats object
simulation_stats = SimulationStats()

pygame.init()
simulation = pygame.sprite.Group()

class TrafficSignal:
    def __init__(self, red, yellow, green):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.signalText = ""
        
class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction, will_turn):
        pygame.sprite.Sprite.__init__(self)
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0
        self.willTurn = will_turn
        self.turned = 0
        self.rotateAngle = 0
        self.waiting_time = 0
        
        # Set default stop position first to ensure it always exists
        self.stop = defaultStop[direction]
        
        # Add the vehicle to the appropriate list
        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1
        self.crossedIndex = 0
        
        path = "images/" + direction + "/" + vehicleClass + ".png"
        self.originalImage = pygame.image.load(path)
        self.image = pygame.image.load(path)

        # Now update stop position based on preceding vehicle if one exists
        if(len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0):   
            try:
                if(direction=='right'):
                    self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].image.get_rect().width - stoppingGap         
                elif(direction=='left'):
                    self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].image.get_rect().width + stoppingGap
                elif(direction=='down'):
                    self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].image.get_rect().height - stoppingGap
                elif(direction=='up'):
                    self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].image.get_rect().height + stoppingGap
            except AttributeError:
                # If previous vehicle doesn't have a stop attribute, use default
                self.stop = defaultStop[direction]
                print(f"Warning: Preceding vehicle has no stop attribute. Using default for {direction}, lane {lane}")
            
        # Set new starting and stopping coordinate
        if(direction=='right'):
            temp = self.image.get_rect().width + stoppingGap    
            x[direction][lane] -= temp
        elif(direction=='left'):
            temp = self.image.get_rect().width + stoppingGap
            x[direction][lane] += temp
        elif(direction=='down'):
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] -= temp
        elif(direction=='up'):
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] += temp
        simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        if(self.direction=='right'):
            if(self.crossed==0 and self.x+self.image.get_rect().width>stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
                # Record statistics when vehicle crosses
                simulation_stats.record_vehicle_completion(self, self.direction)
                if(self.willTurn==0):
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = len(vehiclesNotTurned[self.direction][self.lane]) - 1
            if(self.willTurn==1):
                if(self.lane == 1):
                    if(self.crossed==0 or self.x+self.image.get_rect().width<stopLines[self.direction]+40):
                        if((self.x+self.image.get_rect().width<=self.stop or (currentGreen==0 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.x+self.image.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):               
                            self.x += self.speed
                    else:
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                            self.x += 2.4
                            self.y -= 2.8
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or (self.y>(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].y + vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().height + movingGap))):
                                self.y -= self.speed
                elif(self.lane == 2):
                    if(self.crossed==0 or self.x+self.image.get_rect().width<mid[self.direction]['x']):
                        if((self.x+self.image.get_rect().width<=self.stop or (currentGreen==0 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.x+self.image.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                 
                            self.x += self.speed
                    else:
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                            self.x += 2
                            self.y += 1.8
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or ((self.y+self.image.get_rect().height)<(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].y - movingGap))):
                                self.y += self.speed
            else: 
                if(self.crossed == 0):
                    if((self.x+self.image.get_rect().width<=self.stop or (currentGreen==0 and currentYellow==0)) and (self.index==0 or self.x+self.image.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - movingGap))):                
                        self.x += self.speed
                else:
                    if((self.crossedIndex==0) or (self.x+self.image.get_rect().width<(vehiclesNotTurned[self.direction][self.lane][self.crossedIndex-1].x - movingGap))):                 
                        self.x += self.speed
        elif(self.direction=='down'):
            if(self.crossed==0 and self.y+self.image.get_rect().height>stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
                # Record statistics when vehicle crosses
                simulation_stats.record_vehicle_completion(self, self.direction)
                if(self.willTurn==0):
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = len(vehiclesNotTurned[self.direction][self.lane]) - 1
            if(self.willTurn==1):
                if(self.lane == 1):
                    if(self.crossed==0 or self.y+self.image.get_rect().height<stopLines[self.direction]+50):
                        if((self.y+self.image.get_rect().height<=self.stop or (currentGreen==1 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.y+self.image.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                            self.y += self.speed
                    else:   
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                            self.x += 1.2
                            self.y += 1.8
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or ((self.x + self.image.get_rect().width) < (vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].x - movingGap))):
                                self.x += self.speed
                elif(self.lane == 2):
                    if(self.crossed==0 or self.y+self.image.get_rect().height<mid[self.direction]['y']):
                        if((self.y+self.image.get_rect().height<=self.stop or (currentGreen==1 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.y+self.image.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                            self.y += self.speed
                    else:   
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                            self.x -= 2.5
                            self.y += 2
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or (self.x>(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].x + vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().width + movingGap))): 
                                self.x -= self.speed
            else: 
                if(self.crossed == 0):
                    if((self.y+self.image.get_rect().height<=self.stop or (currentGreen==1 and currentYellow==0)) and (self.index==0 or self.y+self.image.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - movingGap))):                
                        self.y += self.speed
                else:
                    if((self.crossedIndex==0) or (self.y+self.image.get_rect().height<(vehiclesNotTurned[self.direction][self.lane][self.crossedIndex-1].y - movingGap))):                
                        self.y += self.speed
        elif(self.direction=='left'):
            if(self.crossed==0 and self.x<stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
                # Record statistics when vehicle crosses
                simulation_stats.record_vehicle_completion(self, self.direction)
                if(self.willTurn==0):
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = len(vehiclesNotTurned[self.direction][self.lane]) - 1
            if(self.willTurn==1):
                if(self.lane == 1):
                    if(self.crossed==0 or self.x>stopLines[self.direction]-70):
                        if((self.x>=self.stop or (currentGreen==2 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].image.get_rect().width + movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                            self.x -= self.speed
                    else: 
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                            self.x -= 1
                            self.y += 1.2
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or ((self.y + self.image.get_rect().height) <(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].y  -  movingGap))):
                                self.y += self.speed
                elif(self.lane == 2):
                    if(self.crossed==0 or self.x>mid[self.direction]['x']):
                        if((self.x>=self.stop or (currentGreen==2 and currentYellow==0) or self.crossed==1) and (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].image.get_rect().width + movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):                
                            self.x -= self.speed
                    else:
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                            self.x -= 1.8
                            self.y -= 2.5
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or (self.y>(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].y + vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().height +  movingGap))):
                                self.y -= self.speed
            else: 
                if(self.crossed == 0):
                    if((self.x>=self.stop or (currentGreen==2 and currentYellow==0)) and (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].image.get_rect().width + movingGap))):                
                        self.x -= self.speed
                else:
                    if((self.crossedIndex==0) or (self.x>(vehiclesNotTurned[self.direction][self.lane][self.crossedIndex-1].x + vehiclesNotTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().width + movingGap))):                
                        self.x -= self.speed
        elif(self.direction=='up'):
            if(self.crossed==0 and self.y<stopLines[self.direction]):
                self.crossed = 1
                vehicles[self.direction]['crossed'] += 1
                # Record statistics when vehicle crosses
                simulation_stats.record_vehicle_completion(self, self.direction)
                if(self.willTurn==0):
                    vehiclesNotTurned[self.direction][self.lane].append(self)
                    self.crossedIndex = len(vehiclesNotTurned[self.direction][self.lane]) - 1
            if(self.willTurn==1):
                if(self.lane == 1):
                    if(self.crossed==0 or self.y>stopLines[self.direction]-60):
                        if((self.y>=self.stop or (currentGreen==3 and currentYellow==0) or self.crossed == 1) and (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].image.get_rect().height +  movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):
                            self.y -= self.speed
                    else:   
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, self.rotateAngle)
                            self.x -= 2
                            self.y -= 1.2
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or (self.x>(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].x + vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().width + movingGap))):
                                self.x -= self.speed
                elif(self.lane == 2):
                    if(self.crossed==0 or self.y>mid[self.direction]['y']):
                        if((self.y>=self.stop or (currentGreen==3 and currentYellow==0) or self.crossed == 1) and (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].image.get_rect().height +  movingGap) or vehicles[self.direction][self.lane][self.index-1].turned==1)):
                            self.y -= self.speed
                    else:   
                        if(self.turned==0):
                            self.rotateAngle += rotationAngle
                            self.image = pygame.transform.rotate(self.originalImage, -self.rotateAngle)
                            self.x += 1
                            self.y -= 1
                            if(self.rotateAngle==90):
                                self.turned = 1
                                vehiclesTurned[self.direction][self.lane].append(self)
                                self.crossedIndex = len(vehiclesTurned[self.direction][self.lane]) - 1
                        else:
                            if(self.crossedIndex==0 or (self.x<(vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].x - vehiclesTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().width - movingGap))):
                                self.x += self.speed
            else: 
                if(self.crossed == 0):
                    if((self.y>=self.stop or (currentGreen==3 and currentYellow==0)) and (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].image.get_rect().height + movingGap))):                
                        self.y -= self.speed
                else:
                    if((self.crossedIndex==0) or (self.y>(vehiclesNotTurned[self.direction][self.lane][self.crossedIndex-1].y + vehiclesNotTurned[self.direction][self.lane][self.crossedIndex-1].image.get_rect().height + movingGap))):                
                        self.y -= self.speed 

# Initialization of signals with default values
def initialize():
    minTime = randomGreenSignalTimerRange[0]
    maxTime = randomGreenSignalTimerRange[1]
    if(randomGreenSignalTimer):
        ts1 = TrafficSignal(0, defaultYellow, random.randint(minTime,maxTime))
        signals.append(ts1)
        ts2 = TrafficSignal(ts1.red+ts1.yellow+ts1.green, defaultYellow, random.randint(minTime,maxTime))
        signals.append(ts2)
        ts3 = TrafficSignal(defaultRed, defaultYellow, random.randint(minTime,maxTime))
        signals.append(ts3)
        ts4 = TrafficSignal(defaultRed, defaultYellow, random.randint(minTime,maxTime))
        signals.append(ts4)
    else:
        ts1 = TrafficSignal(0, defaultYellow, defaultGreen[0])
        signals.append(ts1)
        ts2 = TrafficSignal(ts1.yellow+ts1.green, defaultYellow, defaultGreen[1])
        signals.append(ts2)
        ts3 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[2])
        signals.append(ts3)
        ts4 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[3])
        signals.append(ts4)
    repeat()

# Print the signal timers on cmd
def printStatus():
    for i in range(0, 4):
        if(signals[i] != None):
            if(i==currentGreen):
                if(currentYellow==0):
                    print(" GREEN TS",i+1,"-> r:",signals[i].red," y:",signals[i].yellow," g:",signals[i].green)
                else:
                    print("YELLOW TS",i+1,"-> r:",signals[i].red," y:",signals[i].yellow," g:",signals[i].green)
            else:
                print("   RED TS",i+1,"-> r:",signals[i].red," y:",signals[i].yellow," g:",signals[i].green)
    print()  

def update_vehicle_waiting_times():
    """Update waiting time only for vehicles that are stopped at a signal"""
    for direction in vehicles:
        if direction == 'crossed':  # Skip the 'crossed' counter
            continue
        for lane in [0, 1, 2]:
            for vehicle in vehicles[direction][lane]:
                if vehicle.crossed == 0:
                    direction_num = {'right': 0, 'down': 1, 'left': 2, 'up': 3}[direction]
                    is_stopped = False
                    if direction_num != currentGreen or currentYellow == 1:
                        is_stopped = True
                    else:
                        try:
                            # Vehicle is stopped if at stop line or blocked by another vehicle ahead
                            if direction == 'right':
                                is_stopped = (vehicle.x + vehicle.image.get_rect().width >= vehicle.stop) or \
                                    (vehicle.index > 0 and vehicles[direction][lane][vehicle.index-1].crossed == 0 and
                                     vehicle.x + vehicle.image.get_rect().width + movingGap >= vehicles[direction][lane][vehicle.index-1].x)
                            elif direction == 'down':
                                is_stopped = (vehicle.y + vehicle.image.get_rect().height >= vehicle.stop) or \
                                    (vehicle.index > 0 and vehicles[direction][lane][vehicle.index-1].crossed == 0 and
                                     vehicle.y + vehicle.image.get_rect().height + movingGap >= vehicles[direction][lane][vehicle.index-1].y)
                            elif direction == 'left':
                                is_stopped = (vehicle.x <= vehicle.stop) or \
                                    (vehicle.index > 0 and vehicles[direction][lane][vehicle.index-1].crossed == 0 and
                                     vehicle.x - movingGap <= vehicles[direction][lane][vehicle.index-1].x + vehicles[direction][lane][vehicle.index-1].image.get_rect().width)
                            elif direction == 'up':
                                is_stopped = (vehicle.y <= vehicle.stop) or \
                                    (vehicle.index > 0 and vehicles[direction][lane][vehicle.index-1].crossed == 0 and
                                     vehicle.y - movingGap <= vehicles[direction][lane][vehicle.index-1].y + vehicles[direction][lane][vehicle.index-1].image.get_rect().height)
                        except AttributeError:
                            is_stopped = False
                            vehicle.stop = defaultStop[direction]
                    if is_stopped:
                        vehicle.waiting_time += 1

def get_waiting_vehicles_count(direction):
    """Returns the number of vehicles waiting at a signal"""
    count = 0
    for lane in [0, 1, 2]:
        for vehicle in vehicles[direction][lane]:
            if vehicle.crossed == 0:
                count += 1
    return count

def get_weighted_waiting_time(vehicle_wait_time):
    """Apply weight to a vehicle's waiting time based on how long it's been waiting"""
    for i, threshold in enumerate(WEIGHT_THRESHOLDS):
        if vehicle_wait_time <= threshold:
            return WEIGHT_VALUES[i]
    return WEIGHT_VALUES[-1]  # Return the highest weight for very long waits

def get_total_waiting_time(direction):
    """Calculate total weighted waiting time for a direction (for signal logic and stats)"""
    total = 0
    for lane in [0, 1, 2]:
        for vehicle in vehicles[direction][lane]:
            if vehicle.crossed == 0:
                weighted_time = get_weighted_waiting_time(vehicle.waiting_time)
                total += weighted_time * vehicle.waiting_time
    return total

def get_total_unweighted_waiting_time(direction):
    """Calculate total unweighted waiting time for a direction (for avg wait time display)"""
    total = 0
    for lane in [0, 1, 2]:
        for vehicle in vehicles[direction][lane]:
            if vehicle.crossed == 0:
                total += vehicle.waiting_time
    return total

def select_next_green():
    """Returns the direction number with the highest total waiting time"""
    max_wait = -1
    max_dir = 0
    for i in range(noOfSignals):
        direction = directionNumbers[i]
        wait = get_total_waiting_time(direction)
        if wait > max_wait:
            max_wait = wait
            max_dir = i
    return max_dir

def should_start_countdown():
    """
    Determine if green light should switch based on wait times
    Returns True when total wait time drops below threshold
    """
    current_direction = directionNumbers[currentGreen]
    current_wait = get_total_waiting_time(current_direction)
    
    # Start countdown if current direction has wait time below threshold
    return current_wait < WAIT_TIME_THRESHOLD

def repeat():
    global currentGreen, currentYellow, nextGreen, countdown_active, countdown_timer
    while signals[currentGreen].green > 0:
        # Check if wait time has dropped below threshold
        if not countdown_active:
            if should_start_countdown():
                # Start countdown to change the light
                countdown_active = True
                countdown_timer = COUNTDOWN_TIME
                signals[currentGreen].green = COUNTDOWN_TIME  # Override remaining green time
                print(f"Starting countdown - wait time below {WAIT_TIME_THRESHOLD}")
        
        # Update countdown timer if active
        if countdown_active:
            countdown_timer = signals[currentGreen].green
            
        # Update statistics each second
        simulation_stats.update(vehicles)
        
        # printStatus()
        updateValues()
        update_vehicle_waiting_times()
        time.sleep(1)
    countdown_active = False
    currentYellow = 1
    print("Switching to yellow light for 2 seconds")

    # Record max crowd at signal change
    simulation_stats.record_crowd_on_signal_change(vehicles, timeElapsed)

    # reset stop coordinates of lanes and vehicles 
    for i in range(0,3):
        for vehicle in vehicles[directionNumbers[currentGreen]][i]:
            vehicle.stop = defaultStop[directionNumbers[currentGreen]]
    
    while signals[currentGreen].yellow > 0:  # while the timer of current yellow signal is not zero
        # printStatus()
        updateValues()
        update_vehicle_waiting_times()  # Update waiting times each tick
        time.sleep(1)
    currentYellow = 0  # set yellow signal off
    
    # reset all signal times of current signal to default/random times
    if randomGreenSignalTimer:
        signals[currentGreen].green = random.randint(randomGreenSignalTimerRange[0], randomGreenSignalTimerRange[1])
    else:
        signals[currentGreen].green = defaultGreen[currentGreen]
    signals[currentGreen].yellow = defaultYellow
    signals[currentGreen].red = defaultRed
       
    # Dynamically select next green based on waiting time
    nextGreen = select_next_green()
    currentGreen = nextGreen
    nextGreen = select_next_green()  # Pre-calculate for next round
    signals[nextGreen].red = signals[currentGreen].yellow + signals[currentGreen].green
    repeat()

# Update values of the signal timers after every second
def updateValues():
    for i in range(0, noOfSignals):
        if(i==currentGreen):
            if(currentYellow==0):
                signals[i].green-=1
            else:
                signals[i].yellow-=1
        else:
            signals[i].red-=1

# Generating vehicles in the simulation
def generateVehicles():
    while(True):
        vehicle_type = random.choice(allowedVehicleTypesList)
        lane_number = random.randint(1,2)
        will_turn = 0
        if(lane_number == 1):
            temp = random.randint(0,99)
            if(temp<40):
                will_turn = 1
        elif(lane_number == 2):
            temp = random.randint(0,99)
            if(temp<40):
                will_turn = 1
        temp = random.randint(0,99)
        direction_number = 0
        dist = [25,50,75,100]
        if(temp<dist[0]):
            direction_number = 0
        elif(temp<dist[1]):
            direction_number = 1
        elif(temp<dist[2]):
            direction_number = 2
        elif(temp<dist[3]):
            direction_number = 3
        Vehicle(lane_number, vehicleTypes[vehicle_type], direction_number, directionNumbers[direction_number], will_turn)
        time.sleep(1)

def showStats():
    totalVehicles = 0
    print('Direction-wise Vehicle Counts')
    for i in range(0,4):
        if(signals[i]!=None):
            print('Direction',i+1,':',vehicles[directionNumbers[i]]['crossed'])
            totalVehicles += vehicles[directionNumbers[i]]['crossed']
    print('Total vehicles passed:',totalVehicles)
    print('Total time:',timeElapsed)
    stats_file = simulation_stats.save_to_file()
    print(f"\nDetailed statistics have been saved to: {stats_file}")
    print("\nKey Statistics:")
    print(f"Average waiting time per vehicle: {simulation_stats.get_avg_waiting_time():.2f} seconds")
    print(f"Maximum crowd at any road: {simulation_stats.max_crowd} (at {simulation_stats.max_crowd_direction}, t={simulation_stats.max_crowd_time}s)")
    print(f"Average vehicles on road: {simulation_stats.get_avg_vehicles_on_road():.2f}")
    print(f"Estimated fuel reduction: {simulation_stats.estimate_fuel_reduction():.2f}%")

def simTime():
    global timeElapsed, simulationTime
    while(True):
        timeElapsed += 1
        time.sleep(1)
        if(timeElapsed==simulationTime):
            showStats()
            os._exit(1) 

class Main:
    global allowedVehicleTypesList
    i = 0
    for vehicleType in allowedVehicleTypes:
        if(allowedVehicleTypes[vehicleType]):
            allowedVehicleTypesList.append(i)
        i += 1
    thread1 = threading.Thread(name="initialization",target=initialize, args=())    # initialization
    thread1.daemon = True
    thread1.start()

    # Colours 
    black = (0, 0, 0)
    white = (255, 255, 255)

    # Screensize 
    screenWidth = 1400
    screenHeight = 800
    screenSize = (screenWidth, screenHeight)

    # Setting background image i.e. image of intersection
    background = pygame.image.load('images/intersection.png')

    screen = pygame.display.set_mode(screenSize)
    pygame.display.set_caption("SIMULATION")

    # Loading signal images and font
    redSignal = pygame.image.load('images/signals/red.png')
    yellowSignal = pygame.image.load('images/signals/yellow.png')
    greenSignal = pygame.image.load('images/signals/green.png')
    font = pygame.font.Font(None, 30)
    thread2 = threading.Thread(name="generateVehicles",target=generateVehicles, args=())    # Generating vehicles
    thread2.daemon = True
    thread2.start()

    thread3 = threading.Thread(name="simTime",target=simTime, args=()) 
    thread3.daemon = True
    thread3.start()

    # Add a statistics display area at the bottom of the screen
    statsCoods = (1100, 100)
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                showStats()
                sys.exit()

        screen.blit(background,(0,0))   # display background in simulation
        
        # display signal and set timer according to current status: green, yellow, or red
        for i in range(0,noOfSignals):
            if(i==currentGreen):
                if(currentYellow==1):
                    signals[i].signalText = signals[i].yellow
                    screen.blit(yellowSignal, signalCoods[i])
                else:
                    # If countdown is active, show countdown instead of regular time
                    if countdown_active and i == currentGreen:
                        signals[i].signalText = countdown_timer
                    else:
                        signals[i].signalText = signals[i].green
                    screen.blit(greenSignal, signalCoods[i])
            else:
                if(signals[i].red<=10):
                    signals[i].signalText = signals[i].red
                else:
                    signals[i].signalText = "---"
                screen.blit(redSignal, signalCoods[i])
        signalTexts = ["","","",""]

        # display signal timer
        for i in range(0,noOfSignals):  
            signalTexts[i] = font.render(str(signals[i].signalText), True, white, black)
            screen.blit(signalTexts[i], signalTimerCoods[i])

        # display the three statistics for each node
        for i in range(0,noOfSignals):
            direction = directionNumbers[i]
            
            # 1. Total vehicles passed (existing)
            passedText = f"Passed: {vehicles[direction]['crossed']}"
            vehicleCountTexts[i] = font.render(passedText, True, black, white)
            screen.blit(vehicleCountTexts[i], vehicleCountCoods[i])
            
            # 2. Current waiting vehicles
            waitingCount = get_waiting_vehicles_count(direction)
            waitingText = f"Waiting: {waitingCount}"
            waitingCountText = font.render(waitingText, True, black, white)
            screen.blit(waitingCountText, waitingVehicleCountCoods[i])
            
            # 3. Cumulative unweighted waiting time (for display)
            waitTime = get_total_unweighted_waiting_time(direction)
            waitTimeText = f"Wait time: {waitTime}"
            waitTimeDisplay = font.render(waitTimeText, True, black, white)
            screen.blit(waitTimeDisplay, waitingTimeCoods[i])

        # display time elapsed
        timeElapsedText = font.render(("Time Elapsed: "+str(timeElapsed)), True, black, white)
        screen.blit(timeElapsedText, timeElapsedCoods)

        # display the vehicles
        for vehicle in simulation:  
            screen.blit(vehicle.image, [vehicle.x, vehicle.y])
            vehicle.move()
        
        # Display key statistics on screen
        avg_wait = simulation_stats.get_avg_waiting_time()
        fuel_reduction = simulation_stats.estimate_fuel_reduction()
        max_crowd = simulation_stats.max_crowd
        max_crowd_dir = simulation_stats.max_crowd_direction if simulation_stats.max_crowd_direction else "-"
        max_crowd_time = simulation_stats.max_crowd_time if simulation_stats.max_crowd_time is not None else "-"
        avg_vehicles_on_road = simulation_stats.get_avg_vehicles_on_road()

        statsText1 = font.render(f"Avg wait time: {avg_wait:.1f} sec", True, black, white)
        statsText2 = font.render(f"Fuel reduction: {fuel_reduction:.1f}%", True, black, white)
        statsText3 = font.render(f"Max crowd: {max_crowd} ({max_crowd_dir}, t={max_crowd_time}s)", True, black, white)
        statsText4 = font.render(f"Vehicles completed: {simulation_stats.total_vehicles_completed}", True, black, white)
        statsText5 = font.render(f"Avg vehicles on road: {avg_vehicles_on_road:.1f}", True, black, white)

        screen.blit(statsText1, (statsCoods[0], statsCoods[1]))
        screen.blit(statsText2, (statsCoods[0], statsCoods[1] + 30))
        screen.blit(statsText3, (statsCoods[0], statsCoods[1] + 60))
        screen.blit(statsText4, (statsCoods[0], statsCoods[1] + 90))
        screen.blit(statsText5, (statsCoods[0], statsCoods[1] + 120))

        pygame.display.update()


Main()