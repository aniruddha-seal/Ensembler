
import numpy as np
import pandas as pd

pd.options.mode.use_inf_as_na = True

from ensembler.util.ensemblerTypes import sampler, condition, Number, Iterable, Union

from ensembler.util import dataStructure as data
from ensembler.potentials import OneD as pot
from ensembler.samplers.stochastic import metropolisMonteCarloIntegrator

from ensembler.system.basic_system import system


class edsSystem(system):
    """
        The EDS-System is collecting and providing information essential to EDS.
        The Trajectory contains s and Eoff values for each step.
        Functions like set_s (or simply access s) or set_eoff (or simply access Eoff) give direct acces to the EDS potential.

    """
    name = "eds system"
    # Lambda Dependend Settings
    state = data.envelopedPStstate
    currentState: data.envelopedPStstate
    potential: pot.envelopedPotential

    # current lambda
    _currentEdsS: float = np.nan
    _currentEdsEoffs: float = np.nan

    def __init__(self, potential: pot.envelopedPotential = pot.envelopedPotential(
        V_is=[pot.harmonicOscillatorPotential(x_shift=2), pot.harmonicOscillatorPotential(x_shift=-2)], Eoff_i=[0, 0]),
                 sampler: sampler = metropolisMonteCarloIntegrator(),
                 conditions: Iterable[condition] = [],
                 temperature: float = 298.0, start_position: Union[Number, Iterable[Number]] = None, eds_s:float=1, eds_Eoff:Iterable[Number]=[0, 0]):
        """
            __init__
                construct a eds-System that can be used to manage a simulation.

        Parameters
        ----------
        potential:  pot.envelopedPotential, optional
            potential function class to be explored by sampling
        sampler: sampler, optional
            sampling method, that allows exploring the potential function
        conditions: Iterable[condition], optional
            conditions that shall be applied to the system.
        temperature: float, optional
            The temperature of the system (default: 298K)
        start_position:
            starting position for the simulation and setup of the system.
        eds_s: float, optional
            is the S-value of the EDS-Potential
        eds_Eoff: Iterable[Number], optional
            giving the energy offsets for the

        """
        ################################
        # Declare Attributes
        #################################

        self._currentEdsS = eds_s
        self._currentEdsEoffs = eds_Eoff
        self.state = data.envelopedPStstate

        super().__init__(potential=potential, sampler=sampler, conditions=conditions, temperature=temperature,
                         start_position=start_position)


        # Output
        self.set_s(self._currentEdsS)
        self.set_Eoff(self._currentEdsEoffs)

    def set_current_state(self, currentPosition: Union[Number, Iterable[Number]],
                          currentVelocities: Union[Number, Iterable[Number]]= 0,
                          currentForce: Union[Number, Iterable[Number]] = 0,
                          current_s: Union[Number, Iterable[Number]]= 0,
                          current_Eoff: Union[Number, Iterable[Number]]= 0,
                          currentTemperature: Number = 298):
        """
            set_current_state
                set s the current state to the given variables.

        Parameters
        ----------
        currentPosition: Union[Number, Iterable[Number]]
            The new Position
        currentVelocities: Union[Number, Iterable[Number]],
            The new Velocities
        currentForce: Union[Number, Iterable[Number]],
            The new Forces of the system
        current_s: Union[Number, Iterable[Number]],
            The new S_value
        current_Eoff: Union[Number, Iterable[Number]],
            The new Energy offsets
        currentTemperature: Union[Number, Iterable[Number]],
            the new temperature.
        """
        self._currentPosition = currentPosition
        self._currentForce = currentForce
        self._currentVelocities = currentVelocities
        self._currentTemperature = currentTemperature

        self._currentEdsS = current_s
        self._currentEdsEoffs = current_Eoff

        self.updateSystemProperties()
        self.updateCurrentState()

    def updateCurrentState(self):
        """
            updateCurrentState
                This function updates the current state from the _current Variables.
        """
        self.currentState = self.state(position=self._currentPosition, temperature=self._currentTemperature,
                                       totEnergy=self._currentTotE,
                                       totPotEnergy=self._currentTotPot, totKinEnergy=self._currentTotKin,
                                       dhdpos=self._currentForce, velocity=self._currentVelocities,
                                       s=self._currentEdsS, Eoff=self._currentEdsEoffs)

    def append_state(self, newPosition, newVelocity, newForces, newS, newEoff):
        """
            append_state
                Append a new state to the trajectory.

        Parameters
        ----------
        newPosition: Union[Number, Iterable[Number]]
            new position for the system
        newVelocity: Union[Number, Iterable[Number]]
            new velocity for the system
        newForces: Union[Number, Iterable[Number]]
            new forces for the system
        newS: Number
            new s-values
        newEoff: Iterable[Number]
            new energy offsets
        """

        self._currentPosition = newPosition
        self._currentVelocities = newVelocity
        self._currentForce = newForces
        self._currentEdsS = newS
        self._currentEdsEoffs = newEoff

        self.updateSystemProperties()
        self.updateCurrentState()

        self.trajectory = self.trajectory.append(self.currentState._asdict(), ignore_index=True)

    @property
    def s(self):
        """
            s
                smoothing parameter for the EDS-potential
        """
        return self._currentEdsS

    @s.setter
    def s(self, s: Number):
        self._currentEdsS = s
        self.potential.set_s(self._currentEdsS)
        self.updateSystemProperties()

    def set_s(self, s: Number):
        """
            set_s
                setting a new s-value to the system.

        Parameters
        ----------
        s: Number
            the new smoothing parameter s

        """
        self.s = s

    @property
    def Eoff(self):
        """
            Eoff
                Energy Offsets for the EDS-potential

        """
        return self._currentEdsEoffs

    @Eoff.setter
    def Eoff(self, Eoff: Iterable[Number]):
        self._currentEdsEoffs = Eoff
        self.potential.Eoff_i = self._currentEdsEoffs
        self.updateSystemProperties()

    def set_Eoff(self, Eoff: Iterable[Number]):
        """
            set_Eoff
                setting new Energy offsets.

        Parameters
        ----------
        Eoff: Iterable[Number]
            vector of new energy offsets

        """
        self.Eoff = Eoff
