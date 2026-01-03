import { useEffect } from 'react';
import { Card, Selector } from 'antd-mobile';
import { usePet } from '../hooks/usePet';

export function PetSwitcher() {
  const { selectedPetId, selectPet, pets } = usePet();

  useEffect(() => {
    // Auto-select first pet if none selected
    if (pets.length > 0 && !selectedPetId) {
      selectPet(pets[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pets.length, selectedPetId]); // Only depend on pets.length and selectedPetId to avoid infinite loops

  if (pets.length === 0) {
    return null;
  }

  const options = pets.map(pet => ({
    label: pet.name,
    value: pet._id,
  }));

  return (
    <Card style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '14px', fontWeight: 500 }}>Животное:</span>
        <Selector
          options={options}
          value={selectedPetId ? [selectedPetId] : []}
          onChange={(arr) => {
            const pet = pets.find(p => p._id === arr[0]);
            selectPet(pet || null);
          }}
          style={{ flex: 1 }}
        />
      </div>
    </Card>
  );
}

