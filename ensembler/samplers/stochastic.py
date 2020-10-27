"""
Module: Sampler
    The sampler module is provides methods exploring the potential functions.

    Stochastic Integrators
"""
import numpy as np
import scipy.constants as const

from ensembler.samplers._basicSamplers import _samplerCls
from ensembler.util.ensemblerTypes import Union, List, Tuple, Number
from ensembler.util.ensemblerTypes import systemCls as systemType
import warnings


class stochasticSampler(_samplerCls):
    '''
    This class is the parent class for all stochastic samplers. The pre-implemented
    stochastic type samplers currently comprise various Monte-Carlo and Langevin Methods.
    '''
    # Params
    minStepSize: Number = None
    step_size_coefficient: Number = 1
    spaceRange: Tuple[Number, Number] = None
    resolution: float = 0.01  # increase the ammount of different possible values = between 0 and 10 there are 10/0.01 different positions. only used with space_range

    fixedStepSize: (Number or List[Number])

    # calculation
    posShift: float = 0

    # Limits:
    _critInSpaceRange = lambda self, pos: self.spaceRange is None or (
            self.spaceRange != None and pos >= min(self.spaceRange) and pos <= max(self.spaceRange))

    def random_shift(self, nDimensions: int) -> Union[float, np.array]:
        """
        randomShift
            This function calculates the shift for the current position.

        Parameters
        ----------
        nDimensions : int
            gives the dimensionality of the position, defining the ammount of shifts.

        Returns
        -------
        Union[float, List[float]]
            returns the Shifts
        """

        # which sign will the shift have?
        sign = np.array([-1 if (x < 50) else 1 for x in np.random.randint(low=0, high=100, size=nDimensions)])

        # Check if there is a space restriction? - converges faster
        if (not isinstance(self.fixedStepSize, type(None))):
            shift = np.array(np.full(shape=nDimensions, fill_value=self.fixedStepSize), ndmin=1)
        elif (not isinstance(self.spaceRange, type(None))):
            shift = np.array(np.multiply(np.abs(np.random.randint(low=np.min(self.spaceRange) / self.resolution,
                                                                  high=np.max(self.spaceRange) / self.resolution,
                                                                  size=nDimensions)), self.resolution), ndmin=1)
        else:
            shift = self.step_size_coefficient * np.array(np.abs(np.random.rand(nDimensions)), ndmin=1)

        # Is the step shift in the allowed area? #Todo: fix min and max for mutliDimensional
        if (self.minStepSize != None and any([s < self.minStepSize for s in shift])):
            self.posShift = np.multiply(sign, np.array([s if (s > self.minStepSize) else self.minStepSize for s in shift]))
        else:
            self.posShift = sign * shift

        return np.squeeze(self.posShift)


class monteCarloIntegrator(stochasticSampler):
    """
    monteCarloIntegrator
        This class implements the classic Monte Carlo samplers.
        It chooses its moves purely randomly. Therefore, the distributions generated by this integrator do not
        resemble the (micro/grand) canonical ensemble. Additionally, no kinetic information can be obtained from
        Monte Carlo samplers.
    """
    name = "Monte Carlo Integrator"

    def __init__(self, space_range: Tuple[Number, Number] = None,
                 step_size_coefficient: Number = 5, minimal_step_size: Number = None,
                 fixed_step_size: Number = None):
        """
        __init__
            This is the Constructor of the MonteCarlo samplers.

        Parameters
        ----------
        space_range : Tuple[Number, Number], optional
            maximal and minimal allowed position for after an integration step.
            If not fullfilled, step is rejected. By default None
        step_size_coefficient: Number, optional
            gives the range of the random numbers. Default is one and therefore values between 1 and -1 are chosen. (Default: 1)
        minimal_step_size : Number, optional
            minimal size of an integration step in any direction, by default None
        fixed_step_size : Number, optional
            this option restrains each integration step to a certain size in each dimension, by default None
        """
        super().__init__()
        self.fixedStepSize = None if (isinstance(fixed_step_size, type(None))) else np.array(fixed_step_size)
        self.minStepSize = minimal_step_size
        self.step_size_coefficient = step_size_coefficient
        self.spaceRange = space_range

    def step(self, system: systemType) -> Tuple[float, None, float]:
        """
        step
            This function is performing an integration step in MonteCarlo fashion.

        Parameters
        ----------
        system : systemType
           A system, that should be integrated.

        Returns
        -------
        Tuple[float, None, float]
            This Tuple contains the new: (new Position, None, position Shift/ force)

        """

        # integrate
        # while no value in spaceRange was found, terminates in first run if no spaceRange
        current_state = system.current_state
        self.oldpos = current_state.position

        while (True):
            self.random_shift(system.nDimensions)
            self.newPos = np.add(self.oldpos, self.posShift)
            # only get positions in certain range or accept if no range
            if (self._critInSpaceRange(self.newPos)):
                break

        if (self.verbose):
            print(str(self.__name__) + ": current position\t ", self.oldpos)
            print(str(self.__name__) + ": shift\t ", self.posShift)
            print(str(self.__name__) + ": newPosition\t ", self.newPos)
            print("\n")

        return np.squeeze(self.newPos), np.nan, np.squeeze(self.posShift)


class metropolisMonteCarloIntegrator(stochasticSampler):
    """
    metropolisMonteCarloIntegrator
        This class is implementing a metropolis monte carlo Integrator.
        In contrast to the Monte Carlo Integrator, that has completely random steps, this sampler has
        limitations to the randomness. This limitation is expressed in the Metropolis Criterion and ensures
        that the microcanonical ensemble is sampled.

        There is a standard Metropolis Criterion implemented, but it can also be exchanged with a different one.

        Default Metropolis Criterion:
            $ decision =  (E_{t} < E_{t-1}) ||  ( rand <= e^{(-1/(R/T*1000))*(E_t-E_{t-1})}$
            with:
                - $R$ as universal gas constant

        The original Metropolis Criterion (Nicholas Metropolis et al.; J. Chem. Phys.; 1953 ;doi: https://doi.org/10.1063/1.1699114):

            $ p_A(E_{t}, E_{t-1}, T) = min(1, e^{-1/(k_b*T) * (E_{t} - E_{t-1})})
            $ decision:  True if( 0.5 < p_A(E_{t}, E_{t-1}, T)) else False
            with:
                - $k_b$ as Boltzmann Constant

    """
    name = "Metropolis Monte Carlo Integrator"
    # Parameters:
    maxIterationTillAccept: float = np.inf  # how often shall the samplers iterate till it accepts a step forcefully
    convergence_limit: int = np.inf  # after reaching a certain limit abort iteration

    # METROPOLIS CRITERION
    ##random part of Metropolis Criterion:
    _default_randomness = lambda self, ene_new, current_state: (
            self._randomness_factor * np.random.rand() <= np.exp(
        -1.0 / (const.gas_constant / 1000.0 * current_state.temperature) * (
                    ene_new - current_state.total_potential_energy)))

    def __init__(self, space_range: tuple = None,
                 step_size_coefficient: Number = 5, minimal_step_size: float = None,
                 fixed_step_size=None,
                 randomness_increase_factor=1.25, max_iteration_tillAccept: int = 10000):
        """
        __init__
            This is the Constructor of the Metropolis-MonteCarlo samplers.


        Parameters
        ----------
        minimal_step_size : Number, optional
            minimal size of an integration step in any direction, by default None
        space_range : Tuple[Number, Number], optional
            maximal and minimal allowed position for after an integration step.
            If not fullfilled, step is rejected. By default None
        fixed_step_size : Number, optional
            this option restrains each integration step to a certain size in each dimension, by default None
        randomness_increase_factor : int, optional
            arbitrary factor, controlling the amount of randomness(the bigger the more random steps), by default 1
        max_iteration_tillAccept : int, optional
            number, after which a step is accepted, regardless its likelihood (turned off if np.inf). By default None
        """
        super().__init__()

        # Integration Step Constrains
        self.fixedStepSize = None if (isinstance(fixed_step_size, type(None))) else np.array(fixed_step_size)
        self.minStepSize = minimal_step_size
        self.step_size_coefficient = step_size_coefficient
        self.spaceRange = space_range

        # Metropolis Criterions
        self._randomness_factor = randomness_increase_factor
        self.maxIterationTillAccept = max_iteration_tillAccept

    ##default Metropolis Criterion
    def metropolis_criterion(self, ene_new, current_state):
        """
        metropolisCriterion
            The metropolis criterion decides if a step is accepted.

        Parameters
        ----------
        ene_new: float
            new energy in case the step is accepted
        current_state: stateType
            state of the current step

        Returns boolean
            defines if step is accepted or not
        -------

        """
        return (ene_new < current_state.total_potential_energy or self._default_randomness(ene_new, current_state))

    def step(self, system: systemType) -> Tuple[float, None, float]:
        """
        step
            This function is performing an Metropolis Monte Carlo integration step.

        Parameters
        ----------
        system : systemType
            A system, that should be integrated.

        Returns
        -------
        Tuple[float, None, float]
            This Tuple contains the new: (new Position, None, position Shift/ force)

        """

        current_iteration = 0
        current_state = system.current_state
        self.oldpos = current_state.position
        nDimensions = system.nDimensions

        # integrate position
        while (current_iteration <= self.convergence_limit and current_iteration <= self.maxIterationTillAccept):  # while no value in spaceRange was found, terminates in first run if no spaceRange
            self.random_shift(nDimensions)

            # eval new Energy
            system._currentPosition = self.oldpos + self.posShift
            system._currentForce = self.posShift

            new_ene = system.potential.ene(system._currentPosition)
            #print(system._currentPosition)

            # MetropolisCriterion
            if (self.maxIterationTillAccept <= current_iteration or ((self._critInSpaceRange(system._currentPosition) and
                                                                   self.metropolis_criterion(new_ene, current_state)))):
                break
            else:  # not accepted
                current_iteration += 1

            if (current_iteration >= self.convergence_limit):
                raise ValueError(
                    "Metropolis-MonteCarlo samplers did not converge! Think about the maxIterationTillAccept")


        self.newPos = self.oldpos
        if (self.verbose):
            print(str(self.__name__) + ": current position\t ", self.oldpos)
            print(str(self.__name__) + ": shift\t ", self.posShift)
            print(str(self.__name__) + ": newPosition\t ", self.newPos)
            print(str(self.__name__) + ": iteration " + str(current_iteration) + "/" + str(self.convergence_limit))
            print("\n")

        return np.squeeze(system._currentPosition), np.nan, np.squeeze(self.posShift)


'''
Langevin stochastic integration
'''


class langevinIntegrator(stochasticSampler):
    """
    This class implements the Position Langevin sampler. In Contrast to the Monte Carlo Methods,
    Langevin integrators provide information on the kinetics of the system.  The Position Langevin
    Integrator does not calculate velocities. Therefore, the kinetic energy is undefined.
    """
    name = "Langevin Integrator"

    def __init__(self, dt: float = 0.005, gamma: float = 50, old_position: float = None):
        """
          __init__
              This is the Constructor of the Langevin samplers.


          Parameters
          ----------
          dt : Number, optional
              time step of an integration, by default 0.005
          gamma : Number, optional
              Friktion constant of the system, by default 50
          old_position : Iterable[Number, Number] of size nDim, optional
              determines the position at step -1, if not set the system will use the velocity to determine this position
          """
        super().__init__()

        self.dt = dt
        self.gamma = gamma
        self._oldPosition = old_position
        self._first_step = True  # only neede for velocity Langevin
        self.R_x = None
        self.newForces = None
        self.currentPosition = None
        self.currentVelocity = None

    def update_positon(self, system):
        """
        Integrate step according to Position Langevin BBK samplers
        Designed after: http://localscf.com/localscf.com/LangevinDynamics.aspx.html

        update position
            This interface function needs to be implemented for a subclass.
            The purpose of this function is to perform one integration step.

        Parameters
        ----------
        system : systemType
           A system, that should be integrated.

        Returns
        -------
        Tuple[float, None]
            This Tuple contains the new: (new Position, new velocity=None)
            for velocity return use langevinVelocityIntegrator

        Raises
        ------
        NotImplementedError
            You need to implement this function in the subclass (i.e. in your samplers)

        """

        nDimensions = system.nDimensions
        # get random number, normal distributed for nDimensions dimentions
        curr_random = np.squeeze(np.random.normal(0, 1, nDimensions))
        # scale random number according to fluctuation-dissipation theorem
        # energy is expected to be in units of k_B
        self.R_x = np.sqrt(2 * system.temperature * self.gamma * system.mass / self.dt) * curr_random
        # calculation of forces:
        self.newForces = -system.potential.force(self.currentPosition)

        # Brünger-Brooks-Karplus samplers for positions
        new_position = (1 / (1 + self.gamma * self.dt / 2)) * (2 * self.currentPosition - self._oldPosition
                                                               + self.gamma * (self.dt / 2) * (self._oldPosition) + (
                                                                       self.dt ** 2 / system.mass) * (
                                                                       self.R_x + self.newForces))

        return new_position, None, curr_random

    def step(self, system):
        """
        step
            This interface function needs to be implemented for a subclass.
            The purpose of this function is to perform one integration step.

        Parameters
        ----------
        system : systemType
           A system, that should be integrated.

        Returns
        -------
        Tuple[float, float, float]
            This Tuple contains the new: (new Position, new velocity, position Shift/ force)

        Raises
        ------
        NotImplementedError
            You need to implement this function in the subclass (i.e. in your samplers)

        """
        # get current positiona and velocity form system class
        self.currentPosition = np.array(system._currentPosition)
        self.currentVelocity = np.array(system._currentVelocities)

        # hirachy: first check if old position is given, if not it takes the velocity from the system class
        # is there no initial velocity a Maxwell-Boltzmann distributed velocity is generated
        if self._oldPosition is None:
            # get old position from velocity, only during initialization
            print("initializing Langevin old Positions\t ")
            print("\n")

            self._oldPosition = self.currentPosition - self.currentVelocity * self.dt

            if(system.nDimensions < len(np.array(self._oldPosition, ndmin=1))):   #this is not such a nice fix, but if multiple states are involved, multiple vels are needed as well.
                self._oldPosition = np.squeeze(self._oldPosition[:system.nDimensions])
        else:
            self._oldPosition = np.array(self._oldPosition)

        # integration step
        new_position, new_velocity, curr_random = self.update_positon(system)
        # update position
        self._oldPosition = self.currentPosition

        #Here we now calculate the force of the unbiased system if reweighting is enabled.
        if system.reweighting:
            #check if the potential has the value origpotential. If yes caluculate the derivative
            try:
                # calculate the force
                orig_force = -system.potential.origPotential.force(self.currentPosition)
            except AttributeError:
                warnings.warn("You did not select an enhanced sampling potential. If you set reweighting=True choose one"
                              "of the available enhanced sampling methods. Otherwise no force will be written in the "
                                 "dhdpos_orig column.")
                orig_force = None


        if (self.verbose):
            print(str(self.__name__) + ": current forces\t ", self.newForces)
            print(str(self.__name__) + ": old Position\t ", self._oldPosition)
            print(str(self.__name__) + ": current_position\t ", self.currentPosition)
            print(str(self.__name__) + ": current_velocity\t ", self.currentVelocity)
            print(str(self.__name__) + ": newPosition\t ", new_position)
            print(str(self.__name__) + ": newVelocity\t ", new_velocity)
            if system.reweigting:
                print(str(self.__name__) + ": oldRandomNumber\t ", curr_random)
                print(str(self.__name__) + ": originalForce\t ", orig_force)
            print("\n")


        if system.reweighting:
            return new_position, new_velocity, self.newForces, curr_random, orig_force
        else:
            return new_position, new_velocity, self.newForces


class langevinVelocityIntegrator(langevinIntegrator):
    """
    This class implements the Velocity Langevin sampler. It can provide information on the kinetics of the system.
    In Contrast to the Position Langevin Integrator, the Velocity Langevin sampler does calculate velocities.
    Therefore, the kinetic energy is definded. It inherits the function step from the Position Langevin Integrator
    and overwrites update_position.
    """

    name = "Velocity Langevin Integrator"

    def update_positon(self, system):
        """
        Integrate step according to Velocity Langevin BKK samplers
        Designed after: http://localscf.com/localscf.com/LangevinDynamics.aspx.html

        update position
            This interface function needs to be implemented for a subclass.
            The purpose of this function is to perform one integration step.

        Parameters
        ----------
        system : systemType
           A system, that should be integrated.

        Returns
        -------
        Tuple[float, None]
            This Tuple contains the new: (new Position, new velocity)

            returns both velocities and positions at full steps

        Raises
        ------
        NotImplementedError
            You need to implement this function in the subclass (i.e. in your samplers)

        """

        # for the first step we have to calculate new random numbers and forces
        # then we can take the one from  the previous  step
        nDimensions = system.nDimensions
        if self._first_step:
            # get random number, normal distributed for nDimensions dimentions
            curr_random = np.squeeze(np.random.normal(0, 1, nDimensions))
            # scale random number according to fluctuation-dissipation theorem
            # energy is expected to be in units of k_B
            self.R_x = np.sqrt(2 * system.temperature * self.gamma * system.mass / self.dt) * curr_random
            # calculate of forces:
            self.newForces = -system.potential.force(self.currentPosition)

            self._first_step = False

        # Brünger-Brooks-Karplus samplers for velocities

        half_step_velocity = (1 - self.gamma * self.dt / 2) * self.currentVelocity + self.dt / (2 * system.mass) * (
                self.newForces + self.R_x)

        full_step_position = self.currentPosition + half_step_velocity * self.dt

        # calculate forces and random number for new position
        # get random number, normal distributed for nDimensions dimentions
        curr_random = np.squeeze(np.random.normal(0, 1, nDimensions))  # for n dimentions
        # scale random number according to fluctuation-dissipation theorem
        # energy is expected to be in units of k_B
        self.R_x = np.sqrt(2 * system.temperature * self.gamma * system.mass / self.dt) * curr_random

        # calculate of forces:
        self.newForces = -system.potential.force(full_step_position)

        # last half step
        full_step_velocity = (1 / (1 + self.gamma * self.dt / 2)) * (
                half_step_velocity + self.dt / (1 * system.mass) * (self.newForces + self.R_x))

        return full_step_position, full_step_velocity
