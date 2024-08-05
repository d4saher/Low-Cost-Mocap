
import React from 'react';
import { Row, Col, Form, Button } from 'react-bootstrap';

interface ControlDroneRowProps {
    droneIndex: number;
    droneSetpoint: string[][];
    setDroneSetpoint: (newDroneSetpoint: string[][]) => void;
    droneArmed: boolean[];
    setDroneArmed: (newDroneArmed: boolean[]) => void;
    motionPreset: string[];
    setMotionPreset: (newMotionPreset: string[]) => void;
    moveToPos: (pos: number[], droneIndex: number) => Promise<void>;
    LAND_Z_HEIGHT: number;
}

const ControlDroneRow = (props: ControlDroneRowProps) => {
    const { droneIndex, droneSetpoint, setDroneSetpoint, droneArmed, setDroneArmed, motionPreset, setMotionPreset, moveToPos, LAND_Z_HEIGHT } = props;
    return (
        <React.Fragment key={droneIndex}>
                  <Row className='pt-4'>
                    <Col xs="3">
                      <h5>Drone {droneIndex}</h5>
                    </Col>
                    <Col className='text-center'>
                      X
                    </Col>
                    <Col className='text-center'>
                      Y
                    </Col>
                    <Col className='text-center'>
                      Z
                    </Col>
                  </Row>
                  <Row>
                    <Col xs={3} className='pt-2'>
                      Setpoint
                    </Col>
                    <Col>
                      <Form.Control
                        value={droneSetpoint[droneIndex][0]}
                        onChange={(event) => {
                          let newDroneSetpoint = droneSetpoint.slice();
                          newDroneSetpoint[droneIndex][0] = event.target.value;
                          setDroneSetpoint(newDroneSetpoint);
                        }}
                      />
                    </Col>
                    <Col>
                      <Form.Control
                        value={droneSetpoint[droneIndex][1]}
                        onChange={(event) => {
                          let newDroneSetpoint = droneSetpoint.slice();
                          newDroneSetpoint[droneIndex][1] = event.target.value;
                          setDroneSetpoint(newDroneSetpoint);
                        }}
                      />
                    </Col>
                    <Col>
                      <Form.Control
                        value={droneSetpoint[droneIndex][2]}
                        onChange={(event) => {
                          let newDroneSetpoint = droneSetpoint.slice();
                          newDroneSetpoint[droneIndex][2] = event.target.value;
                          setDroneSetpoint(newDroneSetpoint);
                        }}
                      />
                    </Col>
                  </Row>
                  <Row className='pt-3'>
                    <Col>
                      <Button
                        size='sm'
                        variant={droneArmed[droneIndex] ? "outline-danger" : "outline-primary"}
                        onClick={() => {
                          let newDroneArmed = droneArmed.slice();
                          newDroneArmed[droneIndex] = !newDroneArmed[droneIndex];
                          setDroneArmed(newDroneArmed);
                        }}
                      >
                        {droneArmed[droneIndex] ? "Disarm" : "Arm"}
                      </Button>
                    </Col>
                    <Col>
                      <Button
                        size='sm'
                        onClick={() => {
                          let newMotionPreset = motionPreset.slice();
                          newMotionPreset[droneIndex] = "setpoint";
                          setMotionPreset(newMotionPreset);
                        }}
                      >
                        Setpoint
                      </Button>
                    </Col>
                    <Col>
                      <Button
                        size='sm'
                        onClick={() => {
                          let newMotionPreset = motionPreset.slice();
                          newMotionPreset[droneIndex] = "circle";
                          setMotionPreset(newMotionPreset);
                        }}
                      >
                        Circle
                      </Button>
                    </Col>
                    <Col>
                      <Button
                        size='sm'
                        onClick={() => {
                          let newMotionPreset = motionPreset.slice();
                          newMotionPreset[droneIndex] = "square";
                          setMotionPreset(newMotionPreset);
                        }}
                      >
                        Square
                      </Button>
                    </Col>
                    <Col>
                      <Button
                        size='sm'
                        onClick={async () => {
                          await moveToPos([0, 0, LAND_Z_HEIGHT], droneIndex);

                          let newDroneArmed = droneArmed.slice();
                          newDroneArmed[droneIndex] = false;
                          setDroneArmed(newDroneArmed);

                          let newMotionPreset = motionPreset.slice();
                          newMotionPreset[droneIndex] = "setpoint";
                          setMotionPreset(newMotionPreset);
                        }}
                      >
                        Land
                      </Button>
                    </Col>
                  </Row>
                </React.Fragment>
    );
};

export default ControlDroneRow;