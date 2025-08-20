#include <Arduino.h>
#include <SoftwareSerial.h>
#include <Wire.h>

SoftwareSerial lidarSerial(2, 3); // LiDAR TX -> D2, RX -> D3

// LiDAR variables
int dist;
int uart[9];
const int HEADER = 0x59;

// MPU6050 variables
const int MPU = 0x68;
float GyroZ;
float yaw = 0;
float GyroErrorZ;
float elapsedTime, currentTime, previousTime;
int c = 0;

// Gyro movement detection
bool gyroMoving = false;
float gyroThreshold = 1.5; // deg/s

void calculate_IMU_error();
void readMPU6050();

void setup() {
  Serial.begin(9600);
  lidarSerial.begin(115200);
  Wire.begin();

  // Wake MPU6050
  Wire.beginTransmission(MPU);
  Wire.write(0x6B);
  Wire.write(0x00);
  Wire.endTransmission(true);

  // Accel ±8g
  Wire.beginTransmission(MPU);
  Wire.write(0x1C);
  Wire.write(0x10);
  Wire.endTransmission(true);

  // Gyro ±1000°/s
  Wire.beginTransmission(MPU);
  Wire.write(0x1B);
  Wire.write(0x10);
  Wire.endTransmission(true);

  delay(20);
  calculate_IMU_error();
  delay(20);
}

void loop() {
  readMPU6050();

  // Read LiDAR
  if (lidarSerial.available()) {
    if (lidarSerial.read() == HEADER) {
      uart[0] = HEADER;
      if (lidarSerial.read() == HEADER) {
        uart[1] = HEADER;
        for (int i = 2; i < 9; i++) {
          uart[i] = lidarSerial.read();
        }
        int check = 0;
        for (int i = 0; i < 8; i++) check += uart[i];
        if (uart[8] == (check & 0xff)) {
          dist = uart[2] + uart[3] * 256;

          if (dist > 70) dist = 70; // Limit

          // Direction
          String direction = "Stationary";
          if (GyroZ > gyroThreshold) direction = "Right";
          else if (GyroZ < -gyroThreshold) direction = "Left";

          // Object detection
          String objStatus = (dist < 70) ? "Detected" : "None";

          // Gyro status
          gyroMoving = abs(GyroZ) > gyroThreshold;
          String gyroStatus = gyroMoving ? "Moving" : "Still";

          // Send to Python
          Serial.print("distance=");
          Serial.print(dist);
          Serial.print(",yaw=");
          Serial.print(yaw);
          Serial.print(",direction=");
          Serial.print(direction);
          Serial.print(",object=");
          Serial.print(objStatus);
          Serial.print(",gyro=");
          Serial.println(gyroStatus);
        }
      }
    }
  }
}

void readMPU6050() {
  previousTime = currentTime;
  currentTime = millis();
  elapsedTime = (currentTime - previousTime) / 1000.0;

  Wire.beginTransmission(MPU);
  Wire.write(0x47);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU, 2, true);
  GyroZ = (Wire.read() << 8 | Wire.read()) / 32.8;
  GyroZ -= GyroErrorZ;

  yaw += GyroZ * elapsedTime;
  if (yaw < 0) yaw += 360;
  if (yaw >= 360) yaw -= 360;
}

void calculate_IMU_error() {
  while (c < 200) {
    Wire.beginTransmission(MPU);
    Wire.write(0x47);
    Wire.endTransmission(false);
    Wire.requestFrom(MPU, 2, true);
    GyroZ = (Wire.read() << 8 | Wire.read()) / 32.8;
    GyroErrorZ += GyroZ;
    c++;
  }
  GyroErrorZ /= 200;
  c = 0;
}
